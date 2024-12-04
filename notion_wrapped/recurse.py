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


@dataclass
class BlockMetadata:
  depth: int
  child_num: int
  block_num: int
  is_main_thread: bool


class NotionRecurser:
  def __init__(self, notion_api_token, max_workers=10, cache_file="cache/notion_cache.json"):
    self.client = NotionClient(notion_api_token)

    self.max_workers = max_workers
    self.current_worker_count = 1

    self.cache_file = Path(cache_file)
    self.blocks_cache = []
    self.block_counter = count()
    self.block_counter_lock = Lock()

  def load_cache(self):
    if self.cache_file.exists():
      self.blocks_cache = []
      with open(self.cache_file) as f:
        for line in f:
          self.blocks_cache.append(json.loads(line))
    else:
      raise ValueError("Cache file does not exist")
    return self.blocks_cache

  def start_recursion(self, parent_block, cache_mode='live', **kwargs):
    with keep.running():
      if 'reducing_function' in kwargs and self.max_workers > 1:
        print("Warning: reducing function might not work as intended with multiple workers.")
      if cache_mode != 'cached' and not isinstance(parent_block, dict):
        parent_block = self.client.get_block(parent_block)
      
      if cache_mode == 'cached':
        self.load_cache()
        if kwargs.get('reducing_function'):
          print(f"reducing function with cached data not yet implemented")

        for i, block_data in enumerate(self.blocks_cache):
          if (kwargs.get('max_blocks') and i > kwargs.get('max_blocks')) or kwargs.get('max_children') and block_data['child_num'] > kwargs.get('max_children'):
            break
          if(kwargs.get('max_depth') and block_data['depth'] > kwargs.get('max_depth')):
            continue
          if kwargs.get('mapping_function'):
            metadata = BlockMetadata(
              depth=block_data['depth'],
              child_num=block_data['child_num'],
              block_num=i, # change to block_data['block_num'] once I recache
              is_main_thread=block_data['is_main_thread']
            )
            kwargs.get('mapping_function')(block_data['block'], metadata)
        
      elif cache_mode == 'save':
        mapping_function = kwargs.pop('mapping_function')
        self.cache_file.write_text('')
        cache_fp = open(self.cache_file, "a")
        
        def save_block_to_cache(block, metadata):
          if mapping_function:
            mapping_function(block, metadata)
          block_data = {
            "block": block,
            **asdict(metadata)
          }
          cache_fp.write(json.dumps(block_data) + "\n")

        try:
          return self._recurse(parent_block, 0, 0, is_main_thread=True, mapping_function=save_block_to_cache, **kwargs)
        finally:
          cache_fp.close()
      else: # cache_mode == 'live':
        try:
          self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
          return self._recurse(parent_block, 0, 0, is_main_thread=True, **kwargs)
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
    mapping_function=None,
    reducing_function=lambda parent, children=None: None,
    is_main_thread=False
  ):
    with self.block_counter_lock:
      block_num = next(self.block_counter)

    if (max_children is not None and child_num > max_children) or (max_blocks is not None and block_num > max_blocks):
      return reducing_function(parent_block)

    if mapping_function:
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
      if not next_cursor:
        block_id = None
  
    return reducing_function(parent_block, child_results)

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