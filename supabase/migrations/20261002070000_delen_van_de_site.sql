-- Het deel van de site dat je kunt kiezen: visa-the-netherlands. Een deel is een pad in
-- scripts/crawl.py (DELEN); alles daarachter hoort erbij. Al toegepast in Supabase.

alter table public.crawl_aanvragen drop constraint crawl_aanvragen_bron_check;
alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_bron_check
  check (bron in ('visa-the-netherlands'));
