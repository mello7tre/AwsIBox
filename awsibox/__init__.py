import logging

logging.basicConfig()
logging.getLogger("botocore").setLevel("CRITICAL")
logger = logging.getLogger("stacksops")
logger.setLevel(logging.INFO)
logger.propagate = False

name = "awsibox"
__version__ = "1.0.2"
