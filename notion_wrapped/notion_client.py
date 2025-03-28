import requests
import time
import sys
from requests.exceptions import ConnectionError, RequestException

database_page_title = "database_page"

class NotionClient:
  def __init__(self, notion_api_token):
    self.error_count = 0
    self.headers = {
      "Authorization": f"Bearer {notion_api_token}",
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28"
    }
    self.max_retries = 5
    self.base_delay = 1

  def make_request(self, method, url, **kwargs):
    while self.error_count <= self.max_retries:
      try:
        response = requests.request(method, url, headers=self.headers, **kwargs)
        if response.status_code == 200:
          self.error_count = 0
          return response.json()
        elif response.status_code == 404 or response.status_code == 400:
          return None
        elif response.status_code == 429:
          retry_after = int(response.headers.get('Retry-After', 60))
          print(f"\n\n\nRate limited, waiting {retry_after} seconds...\n")
          time.sleep(retry_after)
          continue
        else:
          self.error_count += 1
          delay = min(self.base_delay * (2 ** (self.error_count - 1)), 32)
          print(f"\n\n\nERROR\n{response.text}\n\nRetrying in {delay} seconds...\n")
          time.sleep(delay)
          if self.error_count > self.max_retries:
            print("ERROR, EXITING")
            sys.exit(1)
          continue
      except (ConnectionError, RequestException) as e:
        self.error_count += 1
        delay = min(self.base_delay * (2 ** (self.error_count - 1)), 32)
        print(f"\n\n\nConnection Error: {str(e)}\nRetrying in {delay} seconds...\n")
        time.sleep(delay)
        if self.error_count > self.max_retries:
          print("Max retries exceeded, exiting")
          sys.exit(1)
        continue
    return None

  def check_if_base_database(self, id):
    url = f"https://api.notion.com/v1/databases/{id}"
    response = self.make_request("GET", url)
    return response is not None

  def get_block(self, block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    return self.make_request("GET", url)

  def get_block_children(self, block_id, start_cursor=None):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    params = {"start_cursor": start_cursor} if start_cursor else {}
    return self.make_request("GET", url, params=params)

  def query_database(self, database_id, start_cursor=None):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {"start_cursor": start_cursor} if start_cursor else {}
    return self.make_request("POST", url, json=payload)

  def get_user_name(self, user_id):
    url = f"https://api.notion.com/v1/users/{user_id}"
    response = self.make_request("GET", url)
    return response.get('name', 'N/A') if response else 'N/A'
  
  ## This function isn't used for the Notion wrapped program, but can be used with recurse.py for easy interaction with the Notion API to update database properties
  def update_property(self, block, property_name, property_value):
    def update_block_property(block, property_name, property_value):
      if block['object'] == "page":
        block_type = database_page_title
      else:
        block_type = block['type']

      if block_type != database_page_title:
        return None
      
      if property_name == "icon":
        payload = {
          "icon": {
            "type": "emoji",
            "emoji": property_value
          }
        }
        return payload

      property_type = block["properties"][property_name]["type"]
      if property_type == "files":
        payload = {
          "properties": {
            property_name: {
              "files": [
                {
                  "type": "external",
                  "name": "file or url",
                  "external": {
                    "url": property_value
                  }
                }
              ]
            }
          }
        }
      elif property_type == "rich_text":
        payload = {
          "properties": {
            property_name: {
              "rich_text": [
                {
                  "type": "text",
                  "text": {
                    "content": property_value
                  }
                }
              ]
            }
          }
        }
      elif property_type == "number":
        payload = {
          "properties": {
            property_name: {
              "number": int(property_value.replace(',', ''))
            }
          }
        }

      return payload
      

    page_id = block["id"]
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = update_block_property(block, property_name, property_value)
    if payload:
      response = requests.patch(url, headers=self.headers, json=payload)
      return response.status_code == 200
    return False
