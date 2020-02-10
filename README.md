# MandyBot
Custom Discord bot mainly for tracking user statistics

## Requires 
- discord.py
- pymongo
- dotenv
- requests

## Setup
Install and run mongodb and verify that the mongo service will run on restart. The bot uses the default admin credentials for mongo to make configuration and launching the bot as easy as possible.

Create a file called .env and add the following default information to it:

```
# .env
DISCORD_TOKEN=<Token>
MONGODB_URL=localhost:27017
LOGGING_LEVEL=ERROR
```
Then run the create_db.py script to create the default entry for the bot prefixes.

 
If you plan on running the server on a raspi en its recommended that you create a .desktop file in the auto start to automcatically start the server on reboot

This can be done with creating a .desktop file in /home/pi/.config/autostart which will look similar to:

```
[Desktop Entry]
Type=Application
Name=MandyBot
Exec=/usr/bin/python3 <PATH TO DIR>/bot.py
Terminal=true
Hidden=false
```
Terminal is optional, but recommended to set true to check that the bot has actually connected once it has started.
