import requests
import json
import base64
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ansi escapes for colors
RED     = "\033[91m"
GREEN   = "\033[92m"
BLUE    = "\033[94m"
RESET   = "\033[0m"

# both classes yoinked from https://github.com/evilmog/htpclientapi/blob/master/htpapi_example_p3.py
class HashtopolisSection:
    def __init__(self, api, section_name):
        self.api = api
        self.section_name = section_name

    def __call__(self, request, data=None):
        if data is None:
            data = {}
        data.update({"section": self.section_name, "request": request, "accessKey": self.api.api_key})
        response = requests.post(self.api.api_url, json=data)
        return response.json()

# reference: https://github.com/hashtopolis/server/blob/master/doc/user-api/user-api.pdf
class HashtopolisClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.test = HashtopolisSection(self, "test")
        self.user = HashtopolisSection(self, "user")
        self.group = HashtopolisSection(self, "group")
        self.rightgroup = HashtopolisSection(self, "rightgroup")
        self.agent = HashtopolisSection(self, "agent")
        self.agentBinary = HashtopolisSection(self, "agentBinary")
        self.task = HashtopolisSection(self, "task")
        self.supertask = HashtopolisSection(self, "supertask")
        self.hashlist = HashtopolisSection(self, "hashlist")
        self.superhashlist = HashtopolisSection(self, "superhashlist")
        self.file = HashtopolisSection(self, "file")
        self.cracker = HashtopolisSection(self, "cracker")
        self.config = HashtopolisSection(self, "config")

host = "http://localhost:8080"                  # change this - run on hashtopolis server
endpoint = "/api/user.php"                      # user-api endpoint
api_url = f"{host + endpoint}"
load_dotenv()
api_key = os.getenv("HASHTOPOLIS_API_KEY")
client = HashtopolisClient(api_url, api_key)
discord_key = os.getenv("DISCORD_API_KEY")
channel_id = os.getenv("CHANNEL_ID")

def arguments(argv=None):
    parser = argparse.ArgumentParser(description="BHIS Hashtopolis helper script")
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument("-c","--create", action="store_true", help="Create a cracking task")
    group.add_argument("-l","--list", action="store_true", help="List active cracking tasks")
    group.add_argument("-s","--stop", action="store_true", help="Stop a cracking task by task ID")
    group.add_argument("-k","--cracked", action="store_true", help="Obtain cracked hashes by task ID")
    group.add_argument("-u","--upload", metavar="FILE", help="Upload hash file to Hashtopolis")
    parser.add_argument("-m","--mode", metavar="MODE", help="Specify hash mode (Required with --upload)")
    group.add_argument("-d", "--delete", action="store_true", help="Delete an existing hashlist")
    group.add_argument("-o", "--logs", metavar="TASK_ID", help="Obtain the logs from a specified task, hashlist, and agents (if applicable)")

    args = parser.parse_args(argv)

    if args.upload and not args.mode:
        parser.error("uploading hashes requires a specified hash mode (-u hashes.txt -m 5600)")
    return args

def main():
    checkExpired()
    checkErrors()

    args = arguments(sys.argv[1:])      # read in arguments
    if args.create:
        createTask()
    elif args.list:
        tasks = listTasks("all")
        for t in tasks:
            if t["priority"] == 0:
                print(f"{t["taskId"]}: {t["name"]}", "- Stopped")
            else:
                print(f"{t["taskId"]}: {t["name"]}", "- Running")
    elif args.stop:
        stopTask()
    elif args.cracked:
        getCracked()
    elif args.upload:
        if not os.path.isfile(args.upload):
            print(f"Error: File '{args.upload}' does not exist.")
            exit
        else:
            uploadHashes(args.upload, args.mode)
    elif args.delete:
        deleteHashlist()
    elif args.logs:
        logs = getLogs(taskInfo(int(args.logs)))
        for log in logs:
            print(f"({log["timestamp"]}) [{log["logtype"]}]: {log["message"]}")
# primary functions:

def createTask():
    taskname = input(f"Task name: ")

    # setting task deadlines, asking user to verify deadline
    okay = False            # final user acceptance boolean
    while okay == False:
        days = input(f"How many days should the task run? ")
        creation=datetime.now().strftime("%Y-%m-%d")
        date = getDeadline(days)
        deadline=date.strftime("%Y-%m-%d")

        response = input(f"""Task will be marked for expiration on {date.strftime("%B %d, %Y")} ({deadline}).
Is that okay? (y/n): """)
        if response == "y":
            okay = True
            finalname = (f"{taskname}:{creation}_to_{deadline}")
            print(finalname)
        elif response == "n":
            continue
        else:
            print("Invalid input.")
            continue

    # select hashlist
    hashlists = client.hashlist("listHashlists").get("hashlists",[])
    for h in hashlists: print(f"{h["hashlistId"]}: {h["name"]}")

    selection = int(input(f"Select hashlistId: "))
    for h in hashlists:
        if selection == h["hashlistId"]:
            hashlist = h["hashlistId"]
            found = True
            break
    if not found:
        print("Invalid selection.")
    print()

    # select wordlist
    files = []
    wordlists = listFiles(0)
    for i, w in enumerate(wordlists, start=1): print(f"{i}: {w["filename"]}")

    selection = int(input(f"Select wordlist: "))
    if 1 <= selection <= len(wordlists):
        wordlist = wordlists[selection-1]["filename"]
        files.append(wordlists[selection-1]["fileId"])
    else:
        print("Invalid selection.")
    print()

    # select ruleset
    rulesets = listFiles(1)
    ruleset = None

    if not rulesets:
        print("No rulesets available. Skipping...")
    else:
        for i, r in enumerate(rulesets, start=1): print(f"{i}: {r["filename"]}")

        selection = input(f"Select ruleset (press Enter to skip): ")

        if selection.strip() == "":
            ruleset = None
        else:
            selection = int(selection)
            if 1 <= selection <= len(rulesets):
                ruleset = rulesets[selection-1]["filename"]
                files.append(rulesets[selection-1]["fileId"])
            else:
                print("Invalid selection.")
    print()

    # final attack command
    if not ruleset:
        attackcmd = "#HL# -a 0 " + wordlist
    else:
        attackcmd = "#HL# -a 0 " + wordlist + "-r " + ruleset

    # set priority
    priority = int(input("Set task priority: "))
    
    # set max agents - list how many total
    maxagents = 0
    agents = client.agent("listAgents").get("agents", [])

    for i, a in enumerate(agents, start=1): print(f"{a["agentId"]} {a["name"]} {a["devices"][2]}")

    selection = int(input(f"set how many agents? ({i} max) "))
    if selection > 0 and selection <= i:
        maxagents = selection
    else:
        print("Invalid entry")
    
    # get crackerversion id - idk how many will be here if i add more
    crackers = client.cracker("getCracker", {"crackerTypeId": 1})
    versionid = crackers.get("crackerVersions", [{}])[0].get("versionId")

    data = {
        "name": finalname,
        "hashlistId": hashlist,
        "attackCmd": attackcmd,
        "chunksize": 600,
        "statusTimer": 5,
        "benchmarkType": "runtime",
        "color": "00FF80",
        "isCpuOnly": False,
        "isSmall": False,
        "skip": 0,
        "crackerVersionId": versionid,
        "files": files,
        "priority": priority,
        "maxAgents": maxagents,
        "preprocessorId": 0,
        "preprocessorCommand": "",
    }

    taskid = client.task("createTask", data).get("taskId", [])
    print(f"Task created! Task ID: {taskid}")
    checkErrors(taskid)

def listTasks(type):
    tasks = client.task("listTasks").get("tasks", [])

    if type == "all":
        return tasks
    elif type == "running":
        return [t for t in tasks if t["priority"] != 0]
    elif type == "stopped":
        return [t for t in tasks if t["priority"] != 0]
    else:
        return []

def stopTask(task=None):
    tasks = listTasks("running")
    if not tasks:
        print("No running tasks!")
        return
    
    if task is None:
        for t in tasks:
            print(f"{t["taskId"]}: {t["name"]}")

        selection = int(input(f"Select taskId: "))
    else:
        selection = task

    for t in tasks:
        if selection == t["taskId"]:
            # pull agents to unassign them
            agents = taskInfo(t["taskId"]).get("agents", [])
            if agents:
                for a in agents:
                    client.task("taskUnassignAgent", {"agentId": a["agentId"]})

            client.task("setTaskPriority", {"taskId": t["taskId"], "priority": 0}) # setting priority to zero effectively stops the task
            return
    print("Invalid selection.")

def getCracked():
    tasks = listTasks("all")

    for t in tasks:
        print(f"{t["taskId"]}: {t["name"]}")

    selection = int(input(f"Select taskId: "))
    for t in tasks:
        if selection == t["taskId"]:
            cracked = client.task("getCracked", {"taskId": t["taskId"]}).get("cracked", [])
            for c in cracked:
                print(f"{c["hash"]} : {c["plain"]}")
            return
    print("Invalid selection.")

def uploadHashes(file, mode):
    try:
        with open(file, "rb") as f:
            hashes = f.read()

    except Exception as e:
        print(f"Error reading file {e}")
        exit
    
    hashlistname = input(f"Hashlist name: ")
    # print(mode)

    encoded_bytes = base64.b64encode(hashes)
    encoded_str = encoded_bytes.decode("utf-8")
    # print(encoded_str)

    data = {
        "name": hashlistname,
        "isSalted": False,
        "isSecret": False,
        "isHexSalt": False,
        "separator": ":",
        "format": 0,
        "hashtypeId": mode,
        "accessGroupId": 1,
        "data": encoded_str,
        "useBrain": False,
        "brainFeatures": 0,
    }

    hashlistid = client.hashlist("createHashlist", data).get("hashlistId", [])
    print(f"Hashlist created! Hashlist ID: {hashlistid}")

# secondary functions:

def getDeadline(days):
    try:
        days = int(days)
        return datetime.now() + timedelta(days=days)
    
    except ValueError:
        raise ValueError("Days must be an integer.")

def listFiles(type):

    filelist = client.file("listFiles")     # web request
    files = filelist.get("files", [])       # extract json contents

    # for file in files:
    if type == "all":   # list all
        return files
    
    elif type == 0:     # list wordlists
        return [f for f in files if f["fileType"] == 0]
    
    elif type == 1:     # list rules
        return [f for f in files if f["fileType"] == 1]
    
    else:
        return []       # return empty list

def deleteHashlist():
    # select hashlist
    hashlists = client.hashlist("listHashlists").get("hashlists",[])
    for h in hashlists: print(f"{h["hashlistId"]}: {h["name"]}")

    selection = int(input(f"Select hashlistId: "))
    for h in hashlists:
        if selection == h["hashlistId"]:
            found = True
            break
    if not found:
        print("Invalid selection.")
    print()

    response = client.hashlist("deleteHashlist", {"hashlistId": h["hashlistId"]}).get("response", [])
    if response == "OK":
        print("Hashlist deleted successfully!")
    else:
        print("Hashlist deletion failed.")

def checkExpired():
    tasks = listTasks("running")
    now = datetime.now()

    for t in tasks:
        # print(t)
        created, expires = extractDates(t["name"])
        
        if expires < now:
            print(f"{t["taskId"]}. {t["name"]} expired on {expires.strftime("%Y-%m-%d")}.")
            stopTask(t["taskId"])
            # client.task("setTaskPriority", {"taskId": t["taskId"], "priority": 0}) # todo make nicer stoptask function
            # print()
        else:
            continue

def taskInfo(taskid: int):
    tasks = listTasks("all")

    # extract associated hashlist and agents (if running)
    for t in tasks:
        if t["taskId"] == taskid:
            # extract taskid, hashlistid, and agents (if running)
            info = client.task("getTask", {"taskId": t["taskId"]})
            agents = info.get("agents", [])

            created, expires = extractDates(t["name"])

            # return everything
            return {
                "created": created.strftime("%Y-%m-%d") if created else None,
                "expires": expires.strftime("%Y-%m-%d") if expires else None,
                "taskId": info["taskId"],
                "hashlistId": info["hashlistId"],
                "agents": agents
            }
    return None

def getLogs(task=None):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
    headers = {"Authorization": f"Bot {discord_key}"}
    response = requests.get(url, headers=headers)
    messages = response.json()
    
    logs = []
    search = set()

    if task:        
        search.add(str(task["taskId"]))
        search.add(str(task["hashlistId"]))
        for agent in task["agents"]:
            search.add(str(agent.get("agentId", agent)))
        created = datetime.fromisoformat(task["created"])
        expires = datetime.fromisoformat(task["expires"])

    # pull subject and ID out of message
    pattern = r"'([^']+)' \((\d+)\)"

    # iterate in chronological order (newest at bottom)
    for m in reversed(messages):
        logtype = m.get("author", {}).get("username", [])
        message  = m.get("content", "")
        logtime = datetime.fromisoformat(m["timestamp"].replace("Z","")).replace(tzinfo=None)

        if created and logtime < created:
            continue
        if expires and logtime > expires:
            continue
        
        matches = re.findall(pattern, message)
        matchid = {logid for _, logid in matches}

        if not search or matchid.intersection(search):
            logs.append({
                "timestamp": logtime.strftime("%Y-%m-%d %H:%M"), # normlize timestamp
                "logtype": logtype,
                "message": message,
                "subjects": matches
            })

    return logs

def extractDates(name):
    created = None
    expires = None

     # extract task name, creation date, and expiration date
    if ":" in name:
        _, lifetime = name.rsplit(":", 1)
        if "_to_" in lifetime:
            try:
                createdStr, expiresStr = lifetime.split("_to_", 1)
                created = datetime.strptime(createdStr, "%Y-%m-%d")
                expires = datetime.strptime(expiresStr, "%Y-%m-%d")
                return created, expires
            except ValueError:
                return created, expires
    
def checkErrors(taskid: int = None):
    if taskid:
        info = taskInfo(taskid)
        if info is None:
            print(f"Task {taskid} does not exist.")
            return
    else:
        tasks = listTasks("running")            # if no taskid is given, go for all tasks.
        
        for t in tasks:
            info = taskInfo(t["taskId"])
            logs = getLogs(info)

            founderrors = False
            for log in logs:
                if log["logtype"] == "Errors":
                    founderrors = True
                    print(f"Error found for task ID {t["taskId"]}: ({log["timestamp"]}): {log["message"]}")
                    print(f"Stopping task {t["taskId"]}")
                    stopTask(t["taskId"])
                    # since logs per time window are already returned, errors must be from that task.
                    # stop the task and unassign agents

            if not founderrors:
                print(f"No errors found!")
    
def prettyjson(response):
    print(json.dumps(response, indent=4))

if __name__ == "__main__":
    main()
