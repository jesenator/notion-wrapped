import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import count
from pathlib import Path
from threading import Lock
from dataclasses import dataclass, asdict

from wakepy import keep
from .notion_client import NotionClient
from .utils import extract_notion_id


@dataclass
class BlockMetadata:
  depth: int
  child_num: int
  block_num: int
  is_main_thread: bool


class NotionRecurser:
  def __init__(self, notion_api_token, max_workers=10, cache_mode="use-cache", cache_dir="cache"):
    self.client = NotionClient(notion_api_token, cache_mode=cache_mode, cache_dir=cache_dir)

    self.max_workers = max_workers
    self.current_worker_count = 1

    self.block_counter = count()
    self.block_counter_lock = Lock()
    self.current_block_count = 0

  def start_recursion(self, parent_block, **kwargs):
    with keep.running():
      if 'reducing_function' in kwargs and self.max_workers > 1:
        print("Warning: reducing function might not work as intended with multiple workers.")
      if isinstance(parent_block, dict):
        parent_block_obj = parent_block
      else:
        parent_block_extracted = extract_notion_id(parent_block) if '/' in parent_block else parent_block
        if not parent_block_extracted:
          raise ValueError(f"Invalid Notion page ID or URL provided: `{parent_block}`")
        parent_block_obj = self.client.get_block(parent_block_extracted)

      if parent_block_obj is None:
        raise ValueError(f"Parent block not found: `{parent_block}`")
      try:
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        result = self._recurse(parent_block_obj, 0, 0, is_main_thread=True, **kwargs)
        return result
      finally:
        self.executor.shutdown(wait=True)

  def _recurse(
    self,
    parent_block,
    depth,
    child_num,
    max_depth=None,
    max_children=None,
    max_blocks=None,
    mapping_function=lambda block, metadata: None,
    reducing_function=lambda parent, children=None: None,
    map_and_reduce_on_parent=False,
    is_main_thread=False
  ):
    with self.block_counter_lock:
      block_num = next(self.block_counter)
      self.current_block_count = block_num
    if (max_children is not None and child_num > max_children) or (max_blocks is not None and block_num > max_blocks):
      return

    do_map_and_reduce = depth != 0 or map_and_reduce_on_parent

    if do_map_and_reduce:
      mapping_function(parent_block, BlockMetadata(depth, child_num, block_num, is_main_thread))

    if max_depth is not None and (depth + 1) > max_depth:
      return reducing_function(parent_block)

    block_id = parent_block["id"]
    block_object = parent_block['object']
    next_cursor = None
    child_results = []
    child_count = 0

    while block_id:
      if block_object != "page" and (parent_block['type'] == 'unsupported' or (parent_block['type'] == 'synced_block' and parent_block['synced_block'] != None)):
        break
      elif block_object != "page" and parent_block['type'] == "child_database" and self.client.check_if_base_database(block_id):
        response_data = self.client.query_database(block_id, next_cursor)
      elif block_object == "page" or parent_block.get('has_children'):    
        response_data = self.client.get_block_children(block_id, next_cursor)
      else:
        break

      if response_data is None:
        continue

      blocks = response_data.get('results', [])
      futures = []
      for block in blocks:
        if self.current_worker_count < (self.max_workers):
          future = self.executor.submit(self._recurse, block, depth + 1, child_count, max_depth, max_children, max_blocks, mapping_function, reducing_function, False)
          futures.append(future)
          self.current_worker_count += 1
          future.add_done_callback(lambda f: self.decrease_thread_count())
        else:
          child_result = self._recurse(block, depth + 1, child_count, max_depth, max_children, max_blocks, mapping_function, reducing_function, is_main_thread)
          child_results.append(child_result)
        child_count += 1

      for future in as_completed(futures):
        child_result = future.result()
        child_results.append(child_result)

      next_cursor = response_data.get('next_cursor')
      if not next_cursor or (max_blocks is not None and self.current_block_count > max_blocks):
        block_id = None
    if do_map_and_reduce:
      return reducing_function(parent_block, child_results)
    else:
      return reducing_function(None, child_results)

  def decrease_thread_count(self):
    self.current_worker_count -= 1

#### simple example usage ####

# from notion_wrapped import NotionRecurser, Analytics, utils, NotionClient
# block_id = "8f360d9eb53f4129a492a3bf163eb974"
# notion_recurser = NotionRecurser("NOTION_API_TOKEN", max_workers=10)
# word_count = notion_recurser.start_recursion(block_id, max_depth=2, 
# reducing_function=utils.add_word_count)
# print(word_count)
# print("done")