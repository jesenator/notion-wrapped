import sys
from tqdm import tqdm
import argparse
from .analytics import Analytics
from .recurse import NotionRecurser
from . import utils

def main():
  parser = argparse.ArgumentParser(
    description='Notion Wrapped - Generate analytics and visualizations for your Notion workspace',
    epilog='Example: notion-wrapped --notion-token secret_xxx --page-ids abc123'
  )
  
  # Add argument groups for better organization
  required = parser.add_argument_group('required arguments')
  required.add_argument('--notion-token', required=True, 
    help='Notion API token (starts with "secret_"). Get it from https://www.notion.so/my-integrations')
  required.add_argument('--page-ids', nargs='+', required=True, 
    help='One or more Notion page IDs or URLs to analyze')

  # Group optional arguments by category
  analytics_args = parser.add_argument_group('analytics options')
  analytics_args.add_argument('--only-show-pages-in-network-graph', action='store_true', 
    help='Only show pages in network graph, not other blocks')
  analytics_args.add_argument('--no-users', action='store_true',
    help='Disable user information fetching')
  analytics_args.add_argument('--anonymous-network-graph', action='store_true',
    help='Use anonymous network graph')
  analytics_args.add_argument('--word-cloud-as-notion-logo', action='store_true',
    help='Use Notion logo as word cloud mask')
  analytics_args.add_argument('--last-n-years', type=int, metavar='N',
    help='Last N years to consider for Notion wrapped')

  recurser_args = parser.add_argument_group('recursion options')
  recurser_args.add_argument('--max-depth', type=int, metavar='N',
    help='Maximum recursion depth')
  recurser_args.add_argument('--max-children', type=int, metavar='N',
    help='Maximum number of children per block')
  recurser_args.add_argument('--max-blocks', type=int, metavar='N',
    help='Maximum total blocks to process')
  
  # Add API caching options
  cache_args = parser.add_argument_group('API caching options')
  cache_args.add_argument('--cache-mode', choices=["use-cache", "rebuild-cache", "no-cache"], default="use-cache",
    help='Cache mode: use-cache (default), rebuild-cache (clear and rebuild cache), or no-cache (no caching)')
  
  parser.add_argument('--version', action='version',
    version=f'notion-wrapped {__import__("notion_wrapped").__version__}')

  args = parser.parse_args()

  try:
    tqdm.write("\033[91m" + "=" * 40)
    tqdm.write("STARTING NOTION WRAPPED".center(40))
    tqdm.write("=" * 40 + "\033[0m\n")

    analytics = Analytics(
      api_token=args.notion_token,
      show_graphs=False,
      only_show_pages_in_network_graph=args.only_show_pages_in_network_graph,
      get_users=not args.no_users,
      anonymous_network_graph=args.anonymous_network_graph,
      word_cloud_as_notion_logo=args.word_cloud_as_notion_logo,
      last_n_years=args.last_n_years
    )
    notion_recurser = NotionRecurser(
      args.notion_token, 
      max_workers=10,
      cache_mode=args.cache_mode,
    )

    for page_id in args.page_ids:
      notion_recurser.start_recursion(
        page_id,
        mapping_function=analytics.add_block,
        max_depth=args.max_depth,
        max_children=args.max_children,
        max_blocks=args.max_blocks
      )

    analytics.end_of_recursion()

    tqdm.write(f"\n\n\033[95mDone! Open the {analytics.pathname} folder to see the results!\033[0m")
    tqdm.write("\n\033[94mShare your Notion Wrapped on social media! \033[92m#NotionWrapped\033[0m")
    tqdm.write("\n\033[91mNote: I recommend removing permissions from the API key after use\033[0m")

    return 0
  except Exception as e:
    tqdm.write(f"\n\n\033[91mError: {str(e)}\033[0m")
    return 1

if __name__ == "__main__":
  sys.exit(main())