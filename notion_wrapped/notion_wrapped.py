from tqdm import tqdm
import argparse
from .analytics import Analytics
from .recurse import NotionRecurser

def main():
  parser = argparse.ArgumentParser(description='Notion Wrapped Program')

  # required arguments
  parser.add_argument('--notion-token', required=True, help='Notion API token')
  parser.add_argument('--page-ids', nargs='+', required=True, help='Starting page IDs')

  # analytics arguments
  # parser.add_argument('--show-graphs', action='store_true', help='Show graphs during execution'
  parser.add_argument('--only-show-pages-in-network-graph', action='store_true', help='Only show pages in network graph, not other blocks')
  parser.add_argument('--no-users', action='store_true', help='Disable user information fetching')
  parser.add_argument('--anonymous-network-graph', action='store_true', help='Use anonymous network graph')
  parser.add_argument('--word-cloud-as-notion-logo', action='store_true', help='Use Notion logo as word cloud mask')
  parser.add_argument('--last-n-years', type=int, help='Last n years to consider for analytics')

  # recurser arguments
  parser.add_argument('--max-depth', type=int, help='Maximum recursion depth')
  parser.add_argument('--max-children', type=int, help='Maximum number of children per block')
  parser.add_argument('--max-blocks', type=int, help='Maximum total blocks to process')
  parser.add_argument('--cache-mode', choices=['live', 'cached', 'save'], default='live', 
                    help='Cache mode: live (no cache), cached (use cache), or save (save to cache)')
  

  args = parser.parse_args()

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
  notion_recurser = NotionRecurser(args.notion_token, max_workers=10)

  for page_id in args.page_ids:
    page_id = notion_recurser.extract_notion_id(page_id) if '/' in page_id else page_id
    result = notion_recurser.start_recursion(
      page_id,
      mapping_function=analytics.add_block,
      max_depth=args.max_depth,
      max_children=args.max_children,
      max_blocks=args.max_blocks,
      cache_mode=args.cache_mode
    )

  analytics.end_of_recursion()

  tqdm.write(f"\033[95mDone! Open {analytics.pathname} to see the results!\033[0m")

if __name__ == "__main__":
  main()