## Hashtopolis API Wrapper + Added Functionality

Hashtopolis natively lacks task expiration, error handling notifications (within the UI), and automatically unassigning agents to cracking tasks when expired/failed. This is a little API wrapper to unofficially add that functionality!

```
usage: hashy.py [-h] [-c] [-l] [-s] [-k] [-u FILE] [-m MODE] [-d] [-o TASK_ID]

  -c, --create        Create a cracking task
  -l, --list          List active cracking tasks
  -s, --stop          Stop a cracking task by task ID
  -k, --cracked       Obtain cracked hashes by task ID
  -u, --upload FILE   Upload hash file to Hashtopolis
  -m, --mode MODE     Specify hash mode (Required with --upload)
  -d, --delete        Delete an existing hashlist
  -o, --logs TASK_ID  Obtain the logs from a specified task, hashlist, and agents (if applicable)
```

If you want to use this yourself, create an `.env` file with the following:

    HASHTOPOLIS_HOST - your Hashtopolis server, e.g. http://localhost:8080
    HASHTOPOLIS_API_KEY - your Hashtopolis user API key
    DISCORD_API_KEY - bot token, needed every run (the error auto-stop check pulls from Discord every time you run the script, not just with -o/--logs)
    CHANNEL_ID - the Discord channel your Hashtopolis webhook notifications post to
