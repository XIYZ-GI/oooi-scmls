import os
from pathlib import Path

DATA_DIRECTORY = Path(os.environ.get("MCSCAI_DATA_DIR", "/app/data"))
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_BLOCKS = 4096
MAX_AXIS = 128
MAX_VOLUME = 262144
DIRECTIONS = ("negative_y", "positive_y", "negative_z", "positive_z", "negative_x", "positive_x")
PISTON_DIRECTIONS = ("negative_y", "positive_y", "positive_z", "negative_z", "positive_x", "negative_x")
NAMED_DIRECTIONS = {"down": "negative_y", "up": "positive_y", "north": "negative_z", "south": "positive_z", "west": "negative_x", "east": "positive_x"}
BLOCK_KINDS = {"slime_block", "honey_block", "piston", "sticky_piston", "redstone_block", "observer", "iron_block", "light_blue_glazed_terracotta", "glass"}
