# Standard library imports
import re
import time
import hashlib
from datetime import datetime, timedelta
import os
import shutil

# Third-party data/math libraries
import numpy as np
import networkx as nx
from tqdm import tqdm

# Visualization libraries
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pyvis.network import Network
from networkx.drawing.nx_pydot import graphviz_layout
from wordcloud import WordCloud

# NLP libraries
import nltk
import ssl
from nltk.corpus import stopwords

def download_nltk_data():
  try:
    nltk.download('stopwords', quiet=True)
  except Exception as e:
    try:
      _create_unverified_https_context = ssl._create_unverified_context
      ssl._create_default_https_context = _create_unverified_https_context
      nltk.download('stopwords', quiet=True)
    except Exception as e:
      print("Warning: Could not download NLTK stopwords. Word cloud may contain common words.")
      return set(['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i'])
  return set(stopwords.words('english'))

# Local imports
from . import utils
from .utils import database_page_title
from .notion_client import NotionClient

class Analytics:
  def __init__(self, 
              api_token, 
              show_graphs=False, 
              only_show_pages_in_network_graph=False, 
              get_users=True, 
              anonymous_network_graph=False,
              show_filter_menu=False,
              network_dimensions=("100%", "1300px"),
              network_graph_backlinks=False,
              word_cloud_as_notion_logo=False, 
              last_n_years=None,
              pathname="analytics"):

    self.only_show_pages_in_network_graph = only_show_pages_in_network_graph
    self.api_token = api_token
    self.last_n_years = last_n_years
    self.total_word_count = 0
    self.total_block_count = 0

    self.max_recursion_depth = 0
    self.error_count = 0

    self.get_users = get_users
    self.users = {}

    self.pathname = pathname
    self.type_colors = {"paragraph": "#4287f5", "bulleted_list_item": "#42f54b", "numbered_list_item": "#f54242", "to_do": "#f5a442", "heading_3": "#42f5f5", database_page_title: "#f542f5", "divider": "#8c8c8c", "image": "#f5e642", "toggle": "#9b42f5", "column": "#f58c42", "heading_2": "#42f5a4", "column_list": "#a4f542", "callout": "#f54287", "child_page": "#42a4f5", "table_row": "#f5428c", "file": "#8cf542", "code": "#424242", "heading_1": "#f5f542", "child_database": "#42f58c", "quote": "#b342f5", "link_to_page": "#f5b342", "synced_block": "#4242f5", "video": "#f54242", "bookmark": "#42f5b3", "table": "#f542b3", "unsupported": "#666666", "equation": "#b3f542", "embed": "#f58742", "table_of_contents": "#4287f5", "link_preview": "#42f587", "pdf": "#f54287", "audio": "#87f542"}

    os.makedirs(self.pathname, exist_ok=True)
    self.analytics_file = open(f"{self.pathname}/analytics.txt", "w+")
    self.log_file = open(f"{self.pathname}/log.txt", "w+", encoding='utf-8')
    self.start_time = time.time()

    self.show_graphs = show_graphs
    self.anonymous_network_graph = anonymous_network_graph     
    self.show_filter_menu = show_filter_menu # show filter menu disables graphviz layout because when you filter with node x, y positions set it resets to those positions which is annoying
    self.network_dimensions = network_dimensions
    self.network_graph_backlinks = network_graph_backlinks
    self.word_cloud_as_notion_logo = word_cloud_as_notion_logo

    self.client = NotionClient(self.api_token)

    if not self.show_graphs:
      plt.ioff()  # Turn off interactive mode if not showing graphs
    else:
      print("WARNING: Showing graphs only works with max_workers=1, please reduce max_workers to 1 to show graphs")
      exit()

    self.init_time_plot()
    self.init_day_plot()
    self.init_word_cloud()
    self.init_block_type_plot()
    self.init_network_graph()

    self.progress_bar = tqdm(position=1, desc="Recursing", unit="block", leave=True, smoothing=0.05, colour="green") # smoothing 0 is full average, 1 is instant, .3 is deafult

    self.last_file_update = 0
    self.stop_words = download_nltk_data()

  def end_of_recursion(self):
    self.update_file()
    self.analytics_file.seek(0)
    print("\n\n" + self.analytics_file.read())

    print("\nSaving and closing files")
    self.analytics_file.close()

    self.update_time_plot(end=True)
    self.update_day_plot(end=True)
    self.update_word_cloud(end=True)
    self.update_block_type_plot(end=True)
    self.update_network_graph(end=True)

    self.progress_bar.close()
    self.log_file.close()

  def get_complete_day_dict(self):
    min_date = min(self.day_dict.keys())
    max_date = max(self.day_dict.keys())
    date_range = [min_date + timedelta(days=x) for x in range((max_date - min_date).days + 1)]
    return {date: self.day_dict.get(date, 0) for date in date_range}


  def execution_time(self):
    end_time = time.time()
    execution_time = end_time - self.start_time
    hours, rem = divmod(execution_time, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"

  def get_anonymous_id(self, id):
    return hashlib.md5(id.encode()).hexdigest() if self.anonymous_network_graph else id
  
  def get_date_time(self, date_time_str):
    date_string, time_string = date_time_str.split("T")
    date = datetime.strptime(date_string, '%Y-%m-%d').date()
    return date, time_string

  def update_day_dict(self, date):
    if date and date.year >= 2019:
      if date in self.day_dict:
        self.day_dict[date] += 1
      else:
        self.day_dict[date] = 1  
    
  def update_time_array(self, block_time):
    block_hour = int(block_time.split(":")[0]) - 1
    self.time_array[block_hour] = self.time_array[block_hour] + 1

  def update_user_count(self, user_id, action):
    if not self.get_users:
      return

    if user_id not in self.users:
      self.users[user_id] = {"name": self.client.get_user_name(user_id), "created_count": 0, "edited_count": 0}
    self.users[user_id][f"{action}_count"] += 1

  def update_word_counts(self, block_text):
    for word in re.split(r'[\s,;:()\[\]{}|/<>+=_"\'\`]+', block_text.lower()): # Split on whitespace and common punctuation
      word = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', word) # Clean any remaining punctuation at start/end      
      if (word and 
          word not in self.stop_words and 
          not re.match(r'^[-—/]+$', word) and
          word not in ['like', 'also', 'really']): # Skip empty strings, stopwords, and common punctuation
        if word not in self.word_counts:
          self.word_counts[word] = 0
        self.word_counts[word] += 1

  def update_network_counts(self, block, block_id, block_type, block_text, depth):
    if not self.only_show_pages_in_network_graph or block_type in [database_page_title, "child_page"]:
      size = max(1, len(block_text))
      if self.anonymous_network_graph:
        label = " "
      elif len(block_text) > 35:
        label = f"{block_text[:35]}..."
      elif block_text:
        label = block_text
      else:
        label = f"type: {block_type}"
            
      node_color = self.type_colors.get(block_type, "#ffffff")  # White for unknown types
      self.G.add_node(block_id, label=label, size=size, color=node_color, type=block_type if not self.anonymous_network_graph else None, level=depth, shape=("star" if block_type in [database_page_title, "child_database", "child_page"] else "dot"))
      
      parent_type = block['parent']['type']
      if parent_type != 'workspace':
        parent_id = block['parent'][parent_type].replace("-", "")
        parent_id = self.get_anonymous_id(parent_id)
        self.G.add_edge(parent_id, block_id)

        # Handle links in any block with rich_text
        if block_type != "to_remove" and self.network_graph_backlinks and block_type in block and 'rich_text' in block[block_type]:
          for text in block[block_type]['rich_text']:
            linked_id = None
            if text.get('type') == 'mention' and text['mention']['type'] == 'page':
              linked_id = text['mention']['page']['id'].replace("-", "")
            elif text.get('href'):
              href_match = re.search(r'([a-f0-9]{32})', text['href'])
              if href_match:
                linked_id = href_match.group(1)
            
            if linked_id:
              linked_id = self.get_anonymous_id(linked_id)
              if linked_id in self.G:
                self.G.add_edge(block_id, linked_id, weight=0.5, link=True)

        if parent_id in self.G.nodes and 'size' in self.G.nodes[parent_id]:
          previous_size = self.G.nodes[parent_id]['size']
          new_size = previous_size + size
          self.G.add_node(parent_id, size=new_size)
        else:
          self.G.add_node(parent_id, size=size, label="unknown" if not self.anonymous_network_graph else " ", color="#ffffff", type="unknown", level=depth)


  def add_block(self, block, metadata):
    # get useful vars for this function
    block_id = self.get_anonymous_id(block['id'].replace("-", ""))
    block_type = database_page_title if block['object'] == "page" else block['type']

    block_text = utils.get_words(block, just_title=True)
    block_word_count = utils.count_words_in_text(block_text)

    block_created_date, block_created_time = self.get_date_time(block['created_time'])
    block_last_edited_date, block_last_edited_time = self.get_date_time(block['last_edited_time'])

    is_date_too_old = lambda date: self.last_n_years and date < (datetime.now().date() - timedelta(days=365 * self.last_n_years))

    # make sure it is this year's notion wrapped relevant
    if is_date_too_old(block_created_date) and is_date_too_old(block_last_edited_date):
      self.update_network_counts(block, block_id, "to_remove", block_text, metadata.depth)
      return
    elif is_date_too_old(block_created_date):
      block_created_date = None

    # one off updates
    self.total_block_count +=1
    self.total_word_count += block_word_count
    self.max_recursion_depth = max(self.max_recursion_depth, metadata.depth)
    
    self.progress_bar.n = self.total_block_count
    self.progress_bar.update(1)
  
    if block_type not in self.block_type_count:
      self.block_type_count[block_type] = 0
    self.block_type_count[block_type] += 1

    # update data for plots
    self.update_time_array(block_created_time)
    self.update_time_array(block_last_edited_time)

    self.update_day_dict(block_created_date)
    self.update_day_dict(block_last_edited_date)

    self.update_user_count(block['created_by']['id'], 'created')
    self.update_user_count(block['last_edited_by']['id'], 'edited')

    self.update_word_counts(block_text)
    self.update_network_counts(block, block_id, block_type, block_text, metadata.depth)

    # output abreviated block info to terminal
    indenter = "==" if "_page" in block_type else "- "
    block_test_sample = block_text[:35].replace("\n", "\\n")
    block_test_sample += "" if len(block_text) <= 35 else "..."
    
    text_info = f"{block_test_sample} + {block_word_count:<3} word{'' if block_word_count == 1 else 's'}" if block_word_count > 0 else ""
    block_info = f"{(indenter * metadata.depth)[:-1]} {block_type:<10.10} - {block_created_date} - {block_id[:5]} - {text_info}"
    
    # Get color for block type and convert to ANSI escape sequence
    color_hex = self.type_colors.get(block_type, "#ffffff")
    r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (1, 3, 5))    
    tqdm.write(f"\033[38;2;{r};{g};{b}m{block_info}\033[0m")
    self.log_file.write(block_info + "\n")

    current_time = time.time()
    if current_time - self.last_file_update < 5:
      return
    self.last_file_update = current_time

    self.update_file()
    if self.show_graphs and metadata.is_main_thread:   
      self.update_time_plot()
      self.update_day_plot()
      self.update_word_cloud()
      self.update_network_graph()
      self.update_block_type_plot()


  def update_file(self):
    self.analytics_file.truncate(0)
    self.analytics_file.seek(0)

    self.analytics_file.write("Block Type Count:")
    sorted_block_types = sorted(self.block_type_count.items(), key=lambda x: x[1], reverse=True)
    for block_type, count in sorted_block_types:
      self.analytics_file.write(f"\n - {block_type}: {count}")

    self.analytics_file.write(f"\n\nTotal Block Count: {self.total_block_count}")
    self.analytics_file.write(f"\nTotal Word Count: {self.total_word_count}")
    self.analytics_file.write(f"\nMax Recursion Depth: {self.max_recursion_depth}")

    # Calculate time estimates for each component
    block_time = self.total_block_count * (10 / 60) # 10 minutes per block
    word_time = self.total_word_count / 38  # 38 words per minute
    page_time = (self.block_type_count.get('child_page', 0) + self.block_type_count.get('child_database', 0)) * 10 # 10 minutes per page
    database_time = self.block_type_count.get('child_database', 0) * 60 # 60 minutes per database

    time_estimate_minutes = block_time + word_time + page_time + database_time
    self.analytics_file.write(f"\n\nNotion Total Time Estimate (hours / days): {int(time_estimate_minutes / 60)} / {int(time_estimate_minutes / 60 / 24)}")
    
    # Add daily statistics
    if self.day_dict:
      complete_day_dict = self.get_complete_day_dict()
      daily_blocks = list(complete_day_dict.values())
      
      self.analytics_file.write(f"\n\nAverage blocks created or edited per day: {sum(daily_blocks) / len(daily_blocks):.2f}")
      self.analytics_file.write(f"\nMedian blocks created or edited per day: {np.median(daily_blocks):.2f}")
      self.analytics_file.write(f"\nDays with zero blocks created or edited: {sum(1 for blocks in daily_blocks if blocks == 0)}")
      self.analytics_file.write(f"\nTotal range of days using Notion: {len(daily_blocks)}")
    
    self.analytics_file.write(f"\n\nProgram Execution time: {self.execution_time()}")

    self.analytics_file.write(f"\n\nTotal Unique Users: {len(self.users)}")

    self.analytics_file.write(f"\n\nTop Users:")
    sorted_users = sorted(self.users.values(), key=lambda x: x['created_count'], reverse=True)
    for user in sorted_users[:100]:
      self.analytics_file.write(f"\n - {user['name']}: {user['created_count']} / {user['edited_count']} (created / edited)")

    
    self.analytics_file.write(f"\n\nTotal Unique Words: {len(self.word_counts)}")

    self.analytics_file.write(f"\n\nTop 100 Most Common Words (also in word cloud):")
    sorted_word_counts = sorted(self.word_counts.items(), key=lambda x: x[1], reverse=True)
    for word, count in sorted_word_counts[:100]:
      self.analytics_file.write(f"\n - {word}: {count}")

    self.analytics_file.flush()
    self.log_file.flush()



  ############################################################################
  ################## BELOW THIS POINT IS THE PLOTTING CODE ##################
  ############################################################################

  ############################### network graph ############################
  def init_network_graph(self):
    self.G = nx.DiGraph()  # Create a directed graph
    if self.show_graphs:
      plt.ion()
    self.network_fig, self.network_ax = plt.subplots(figsize=(15, 10))
    self.network_ax.set_title('Network Graph')
    self.network_ax.axis('off')
    
    # Initialize empty network plot
    self.pos = nx.spring_layout(self.G, k=2, iterations=50)  # k controls spacing
    self.network_nodes = nx.draw_networkx_nodes(self.G, self.pos, node_color="lightblue", node_size=50)
    self.network_edges = nx.draw_networkx_edges(self.G, self.pos, edge_color="gray", arrows=True)
    self.network_labels = nx.draw_networkx_labels(self.G, self.pos, {})

  def adjust_node_sizes(self, sizes):
    if np.any(np.isnan(sizes)) or np.any(np.isinf(sizes)) or len(sizes) == 0:
      return np.full_like(sizes, 50)

    sizes = np.array(sizes)
    new_min = 10
    new_max = 125
    k = 10

    normalized = (sizes - min(sizes)) / (max(sizes) - min(sizes))
    logged = np.log(1 + normalized * k) / np.log(1 + k)
    rescaled = logged * (new_max - new_min) + new_min

    return rescaled

  def update_network_graph(self, end=False):
    if end:
      print("\nProcessing network graph")
      
      # Find nodes to remove (non-child_page nodes)
      types_to_prune = ['column', 'column_list', 'divider', "to_remove"]
      types_to_not_prune = ['child_page', 'child_database', database_page_title]

      print("Removing non-child_page nodes")
      nodes_to_remove = []
      for node in self.G.nodes():
        node_type = self.G.nodes[node].get('type', 'unknown')
        # if node_type not in types_to_not_prune:
        if node_type in types_to_prune:

          # For each non-child_page node, connect its predecessors to its successors
          predecessors = list(self.G.predecessors(node))
          successors = list(self.G.successors(node))

          for pred in predecessors: # likely only one
            added_size = 0

            for succ in successors:
              self.G.add_edge(pred, succ)
              added_size += self.G.nodes[succ].get('size', 0)
            self.G.nodes[pred]['size'] = self.G.nodes[pred]['size'] + added_size
          nodes_to_remove.append(node)
      
      # Remove the non-child_page nodes
      for node in nodes_to_remove:
        self.G.remove_node(node)

      print('Converting networkx to pyvis')
      net = Network(width=self.network_dimensions[0], height=self.network_dimensions[1], bgcolor="black", font_color="white", filter_menu=self.show_filter_menu)
      print('Calculating node positions')

      pos = {}
      if not self.show_filter_menu:
        # Create a copy of the graph without labels for layout calculation (it caused errors)
        G_layout = self.G.copy()
        nx.set_node_attributes(G_layout, '', 'label')
        try:
          pos = nx.nx_agraph.graphviz_layout(G_layout, prog="twopi")

          print('Centering positions around (0,0)')      
          xs = [coord[0] for coord in pos.values()]
          ys = [coord[1] for coord in pos.values()]
          center_x = (max(xs) + min(xs)) / 2
          center_y = (max(ys) + min(ys)) / 2

          pos = {node: (x - center_x, y - center_y) for node, (x, y) in pos.items()}
        except Exception as e:
          print(f"WARNING: Graphviz not installed, falling back to default layout. Please install graphviz to get a better inital layout (makes the most difference for larger graphs).")

      # Configure physics options
      # 0.5 theta is good for smaller graphs, 1 is good for larger graphs (I think?)
      net.set_options("""
        const options = {
          "configure": {
            "enabled": true,
            "filter": ["physics"]
          },
          "edges": {
            "color": {
              "inherit": "both"
            },
            "selfReferenceSize": null,
            "selfReference": {
              "angle": 0.7853981633974483
            },
            "smooth": {
              "forceDirection": "none"
            }
          },
          "physics": {
            "enabled": true,
            "barnesHut": {
              "theta": 0.5,
              "gravitationalConstant": -6000,
              "centralGravity": 0.3,
              "springLength": 95,
              "springConstant": 0.04,
              "damping": 0.09,
              "avoidOverlap": 0.1
            },
            "maxVelocity": 50,
            "minVelocity": 0.75,
            "timestep": 0.5,
            "solver": "barnesHut",
            "stabilization": {
              "enabled": true,
              "iterations": 1000,
              "updateInterval": 25,
              "fit": true
            }
          }
        }
      """)

      print('Converting networkx to pyvis')
      net.from_nx(self.G)

      print('Calculating node sizes')
      sizes = self.adjust_node_sizes([node.get('size', 1) for node in net.nodes])

      print('Converting size and colors and titles to pyvis')
      for i, node in enumerate(net.nodes):
        node['size'] = int(sizes[i])  # Scale down for pyvis
        node['color'] = self.G.nodes[node['id']].get('color', '#ffffff')
        node_type = self.G.nodes[node['id']].get('type', 'unknown')
        if not self.anonymous_network_graph:
          node['title'] = f"{node['label']}\ntype: {node_type}\nID: {node['id']}\nDepth: {node['level']}"
        node_id = node['id']
        if node_id in pos:
          # Scale positions to PyVis coordinates
          node['x'] = pos[node_id][0] * 40 # was 25 then 50
          node['y'] = pos[node_id][1] * 40 # was 25 then 50
      
      print("Writing network graph to html")
      net.write_html("temp_network_graph.html") # the pyvis library doesn't let you save the file in a different directory
      shutil.move("temp_network_graph.html", f"{self.pathname}/network_graph.html")


  ########################### time plot ###########################
  def init_time_plot(self):
    self.time_array = np.zeros(24)
    if self.show_graphs:
      plt.ion()
    self.time_fig, self.time_ax = plt.subplots()
    
    # Get a list of colors from type_colors, cycling if needed to reach 24 colors
    colors = list(self.type_colors.values())
    colors = colors * (24 // len(colors) + 1)  # Repeat colors if needed
    colors = colors[:24]  # Take exactly 24 colors
    
    self.time_bars = self.time_ax.bar(range(24), self.time_array, color=colors)
    self.time_ax.set_ylim(0, 1)
    self.time_ax.set_xlabel('Hour of Day')
    self.time_ax.set_ylabel('Number of Blocks')
    self.time_ax.set_title('Average blocks created or edited per hour of day')
    
    self.time_ax.set_xticks(range(24))
    self.time_ax.set_xticklabels([f'{i:02d}' for i in range(24)], rotation=45)

  def update_time_plot(self, end=False):
    if not self.day_dict:
      return
      
    num_days = len(self.get_complete_day_dict())
    normalized_time_array = self.time_array / num_days
    
    for bar, height in zip(self.time_bars, normalized_time_array):
      bar.set_height(height)
    self.time_ax.set_ylim(0, max(normalized_time_array) * 1.2)
    
    if self.show_graphs:
      self.time_fig.canvas.draw()
      self.time_fig.canvas.flush_events()
      plt.pause(0.1)
    if end:
      print("Saving time plot")
      self.time_fig.tight_layout()  # Adjust layout to prevent label cutoff
      self.time_fig.savefig(f"{self.pathname}/time_plot.png", dpi=300, bbox_inches='tight')


  ########################### day plot ###########################
  def init_day_plot(self):
    self.day_dict = {}  # Dictionary to store the number of blocks per day
    if self.show_graphs:
      plt.ion()
    self.dates = []
    self.values = []
    plt.ion()
    self.day_fig, self.day_ax = plt.subplots(figsize=(20, 8))
    self.day_line, = self.day_ax.plot(self.dates, self.values, 'o-')
    self.day_ax.set_xlabel('Date')
    self.day_ax.set_ylabel('Number of Blocks')
    self.day_ax.set_title('Line Graph of Blocks Created or Edited Per Day')
    self.day_ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    self.day_fig.autofmt_xdate()  # Rotate date labels
    # self.day_ax.set_xticklabels(self.dates, rotation=45, ha='right')

  def update_day_plot(self, end=False):
    # Update the data for plotting
    self.dates = sorted(self.day_dict.keys())
    self.values = [self.day_dict[date] for date in self.dates]
    self.day_line.set_data(self.dates, self.values)
    self.day_ax.set_ylim(0, min(max(self.values) * 1.2, 700))  # Set y-axis limits
    self.day_ax.relim()
    self.day_ax.autoscale_view()
    if self.show_graphs:
      self.day_fig.canvas.draw()
      self.day_fig.canvas.flush_events()
      plt.pause(0.1)
    if end:
      print("Saving day plot")
      self.day_fig.tight_layout()
      self.day_fig.savefig(f"{self.pathname}/day_plot.png", dpi=300, bbox_inches='tight')


  ########################### word cloud ###########################
  def init_word_cloud(self):
    self.word_counts = {}
    if self.show_graphs:
      plt.ion()
    self.cloud_fig, self.cloud_ax = plt.subplots(figsize=(20, 16))
    self.cloud_ax.set_title('Word Cloud')
    self.cloud_image = self.cloud_ax.imshow(np.zeros((10, 10)), cmap='viridis')
    self.cloud_ax.axis('off')

    def make_notion_logo_mask():
      import requests
      from PIL import Image
      from io import BytesIO
      
      response = requests.get('https://upload.wikimedia.org/wikipedia/commons/4/45/Notion_app_logo.png')
      notion_logo = np.array(Image.open(BytesIO(response.content)).convert("RGB"))
      mask = notion_logo[:, :, 0]
      mask = 255 - mask
      return mask

    self.word_cloud = WordCloud(
      width=1500,
      height=1500,
      background_color='black',
      max_words=400,
      prefer_horizontal=0.9,
      scale=2,
      mask=make_notion_logo_mask() if self.word_cloud_as_notion_logo else None,
      colormap=plt.matplotlib.colors.ListedColormap(list(self.type_colors.values()))
    )

  def update_word_cloud(self, end=False):
    if not self.word_counts:
      return
      
    wordcloud = self.word_cloud.generate_from_frequencies(self.word_counts)
    self.cloud_image.set_array(wordcloud.to_array())
    self.cloud_fig.patch.set_facecolor('black')
    self.cloud_ax.set_facecolor('black')
    if self.show_graphs:
      self.cloud_fig.canvas.draw()
      self.cloud_fig.canvas.flush_events()
      plt.pause(0.1)
    if end:
      print("Saving word cloud")
      self.cloud_fig.tight_layout()
      self.cloud_fig.savefig(f"{self.pathname}/word_cloud.png", dpi=300, bbox_inches='tight', facecolor='black')


  ########################### block type plot ###########################
  def init_block_type_plot(self):
    self.block_type_count = {}
    if self.show_graphs:
      plt.ion()
    self.block_type_fig, self.block_type_ax = plt.subplots(figsize=(32, 5))
    self.block_type_ax.set_title('Block Type Count')
    self.block_type_ax.set_xlabel('Block Type')
    self.block_type_ax.set_ylabel('Count')
    self.block_type_bars = self.block_type_ax.bar([], [])
    self.block_type_ax.set_xticklabels([])

  def update_block_type_plot(self, end=False):
    sorted_items = sorted(self.block_type_count.items(), key=lambda x: x[1])
    block_types, counts = zip(*sorted_items) if sorted_items else ([], [])

    self.block_type_ax.clear()
    self.block_type_ax.set_title('Block Type Count')
    self.block_type_ax.set_xlabel('Block Type')
    self.block_type_ax.set_ylabel('Count')
    
    # Use the type_colors for the bars
    colors = [self.type_colors.get(bt, "#ffffff") for bt in block_types]
    bars = self.block_type_ax.bar(block_types, counts, color=colors)

    self.block_type_ax.set_xticks(range(len(block_types)))
    self.block_type_ax.set_xticklabels(block_types, rotation=45, ha='right')

    for bar, count in zip(bars, counts):
      height = bar.get_height()
      self.block_type_ax.text(bar.get_x() + bar.get_width() / 2, height, f'{count}', ha='center', va='bottom')

    if self.show_graphs:
      self.block_type_fig.canvas.draw()
      self.block_type_fig.canvas.flush_events()
      plt.pause(0.1)
    if end:
      print("Saving block type plot")
      self.block_type_fig.tight_layout()
      self.block_type_fig.savefig(f"{self.pathname}/block_type_plot.png", dpi=300, bbox_inches='tight')

