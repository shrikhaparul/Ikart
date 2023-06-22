"""script for general purpose methods like log, audit, connections etc..."""
import logging
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# custom log function for framework
def initiate_logging(project: str, log_loc: str) -> bool:
    """Function to initiate log file which will be used across framework"""
    try:
        log_file_nm = project + '.log'
        new_file1 = log_loc + log_file_nm
        # create formatter & how we want ours logs to be formatted
        format_str = '%(asctime)s | %(name)-10s | %(processName)-12s | %(funcName)-22s |\
        %(levelname)-5s | %(message)s'
        formatter = logging.Formatter(format_str)
        logging.basicConfig(filename=new_file1, filemode='a',
                            level=logging.INFO, format=format_str)
        st_handler = logging.StreamHandler()  # create handler and set the log level
        st_handler.setLevel(logging.INFO)
        st_handler.setFormatter(formatter)
        logging.getLogger().addHandler(st_handler)
        return True
    except Exception as ex:
        logging.error('UDF Failed: initiate_logging failed')
        raise ex

# reading the connection.json file and passing the connection details as dictionary
def get_config_section(config_path:str) -> dict:
    """reads the connection file and returns connection details as dict for
       connection name you pass it through the json
    """
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            logging.info("fetching connection details")
            json_data = json.load(jsonfile)
            logging.info("reading connection details completed")
            # print("connection established")
            return dict(json_data["connection_details"].items())
    except Exception as error:
        logging.exception("get_config_section() is %s.", str(error))
        raise error

# # reading the connection.json file and passing the connection details as dictionary
# def get_config_section(config_path:str, conn_nm: str) -> dict:
#     """reads the connection file and returns connection details as dict for
#        connection name you pass it through the json
#     """
#     try:
#         with open(config_path,'r', encoding='utf-8') as jsonfile:
#             logging.info("fetching connection details")
#             json_data = json.load(jsonfile)
#             logging.info("reading connection details completed")
#             # print("connection established")
#             return dict(json_data[conn_nm].items())
#     except Exception as error:
#         logging.exception("get_config_section() is %s.", str(error))
#         raise error

# def decrypt(edata):
#     """password decryption function"""
#     try:
#         crypto_key= '8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
#         crypto_iv= 'rBEssDfxofOveRxR'
#         block_size=16

#         key = bytes(crypto_key, 'utf-8')
#         value = bytes(crypto_iv, 'utf-8')

#         # Add "=" padding back before decoding
#         edata = base64.urlsafe_b64decode(edata + '=' * (-len(edata) % 4))
#         aes = AES.new(key, AES.MODE_CBC, value)
#         return unpad(aes.decrypt(edata), block_size).decode("utf-8")
#     except Exception as error:
#         logging.exception("decrypt() is %s.", str(error))
#         raise error

def decrypt(data):
    '''function to decrypt the data'''
    KEY = b'8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
    IV = b'rBEssDfxofOveRxR'
    aesgcm = AESGCM(KEY)
    decrypted = aesgcm.decrypt(IV, bytes.fromhex(data), None)
    return decrypted.decode('utf-8')
