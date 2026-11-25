import logging

logging.basicConfig()
logging.getLogger("botocore").setLevel("CRITICAL")
logger = logging.getLogger("awsibox")
logger.setLevel(logging.INFO)

name = "awsibox"
__version__ = "1.0.2"
