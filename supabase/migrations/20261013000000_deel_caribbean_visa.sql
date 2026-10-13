-- Tweede deel van de site: caribbean-visa (pad /caribbean-visa, zie DELEN in scripts/crawl.py).
-- Nog toe te passen in Supabase (SQL Editor).

alter table public.crawl_aanvragen drop constraint crawl_aanvragen_bron_check;
alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_bron_check
  check (bron in ('visa-the-netherlands', 'caribbean-visa'));
