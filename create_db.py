import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URL'))

db = client['mandybot']

db.guildstats.insert_one({'_name': '_mandybot_prefixes', '_mandybot_prefixes': {}})
