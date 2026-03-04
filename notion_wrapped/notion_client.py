import requests
import time
import sys
from requests.exceptions import ConnectionError, RequestException, ReadTimeout
import requests_cache
from pathlib import Path
import sqlite3

database_page_title = "database_page"

class NotionClient:
  def __init__(self, notion_api_token, cache_mode="use-cache", cache_dir="cache", timeout=20):
    self.error_count = 0
    self.headers = {
      "Authorization": f"Bearer {notion_api_token}",
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28"
    }
    self.max_retries = 5
    self.base_delay = 1
    self.timeout = timeout

    # Set up caching
    self.cache_mode = cache_mode
    if self.cache_mode != "no-cache":
      cache_dir_path = Path(cache_dir)
      cache_dir_path.mkdir(parents=True, exist_ok=True)
      self.session = requests_cache.CachedSession(
        cache_name=str(cache_dir_path),
        backend='filesystem',
        expire_after=None,  # Cache never expires
        use_cache_dir=False,  # Don't use cache directory, use our specified path
        cache_control=True,
        stale_if_error=True,
        allowable_methods=('GET', 'POST'),  # Allow caching of POST requests
      )
      self.session.headers.update(self.headers)

      if self.cache_mode == "rebuild-cache":
        self.session.cache.clear()
    else:
      self.session = requests.Session()
      self.session.headers.update(self.headers)

  def make_request(self, method, url, **kwargs):
    kwargs.setdefault('timeout', self.timeout)
    while self.error_count <= self.max_retries:
      try:
        if self.cache_mode != "no-cache":
          try:
            response = self.session.request(method, url, **kwargs)
          except (sqlite3.InterfaceError, sqlite3.OperationalError) as e:
            print(f"\n\n\nCache operation failed: {str(e)}. Falling back to non-cached request.\n\n\n")
            response = requests.request(method, url, headers=self.headers, **kwargs)
        else:
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
      except (ConnectionError, ReadTimeout, RequestException) as e:
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

  def query_database(self, database_id, start_cursor=None, sorts=None):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {}
    if start_cursor:
      payload["start_cursor"] = start_cursor
    if sorts:
      payload["sorts"] = sorts
    return self.make_request("POST", url, json=payload)

  def get_user_name(self, user_id):
    url = f"https://api.notion.com/v1/users/{user_id}"
    response = self.make_request("GET", url)
    return response.get('name', 'N/A') if response else 'N/A'

  ## These functions aren't used for the Notion wrapped program, but can be used with recurse.py for easy interaction with the Notion API to update database properties

  def upload_file(self, file_path, content_type="image/png"):
    create_upload_url = "https://api.notion.com/v1/file_uploads"
    filename = Path(file_path).name
    
    create_upload_payload = {
      "mode": "single_part",
      "filename": filename,
      "content_type": content_type
    }
    
    response = requests.post(create_upload_url, headers=self.headers, json=create_upload_payload, timeout=self.timeout)
    if response.status_code != 200:
      raise Exception(f"Failed to create file upload: {response.text}")
    
    upload_data = response.json()
    upload_url = upload_data["upload_url"]
    file_upload_id = upload_data["id"]
    
    with open(file_path, "rb") as image_file:
      upload_headers = {
        "Authorization": self.headers["Authorization"],
        "Notion-Version": self.headers["Notion-Version"]
      }
      files = {"file": (filename, image_file, content_type)}
      upload_response = requests.post(upload_url, files=files, headers=upload_headers, timeout=self.timeout)
    
    if upload_response.status_code != 200:
      raise Exception(f"Failed to upload file data: {upload_response.text}")
    
    return file_upload_id

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
        if property_value.startswith("file_upload:"):
          file_upload_id = property_value.replace("file_upload:", "")
          payload = {
            "properties": {
              property_name: {
                "files": [
                  {
                    "type": "file_upload",
                    "file_upload": {
                      "id": file_upload_id
                    }
                  }
                ]
              }
            }
          }
        else:
          payload = {
            "properties": {
              property_name: {
                "files": [
                  {
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
      response = requests.patch(url, headers=self.headers, json=payload, timeout=self.timeout)
      return response.status_code == 200
    return False
