import requests
import time
import sys

database_page_title = "database_page"

class NotionClient:
  def __init__(self, notion_api_token):
    self.error_count = 0
    self.headers = {
      "Authorization": f"Bearer {notion_api_token}",
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28"
    }

  def handle_response(self, response):
    if response.status_code == 200:
      self.error_count = 0
      return response.json()
    elif response.status_code == 429:
      retry_after = int(response.headers.get('Retry-After', 60))
      time.sleep(retry_after)
      return None
    else:
      self.error_count += 1
      if self.error_count > 5:
        print("ERROR, EXITING")
        sys.exit(1)
      print(f"\n\n\nERROR\n{response.text}\n\nTrying again\n")
      time.sleep(1)
      return None

  def check_if_base_database(self, id):
    url = f"https://api.notion.com/v1/databases/{id}"
    response = requests.get(url, headers=self.headers)
    return response.status_code == 200

  def get_block(self, block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    response = requests.get(url, headers=self.headers)
    return self.handle_response(response)

  def get_block_children(self, block_id, start_cursor=None):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    params = {"start_cursor": start_cursor} if start_cursor else {}
    response = requests.get(url, headers=self.headers, params=params)
    return self.handle_response(response)

  def query_database(self, database_id, start_cursor=None):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {"start_cursor": start_cursor} if start_cursor else {}
    response = requests.post(url, headers=self.headers, json=payload)
    return self.handle_response(response) 

  def get_user_name(self, user_id):
    url = f"https://api.notion.com/v1/users/{user_id}"
    response = requests.get(url, headers=self.headers)
    response_json = response.json()
    return response_json.get('name', 'N/A')
  
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
