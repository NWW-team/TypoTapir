-- Derde deel van de site: making-appointment (pad /making-appointment, zie DELEN in
-- scripts/crawl.py). Al toegepast in Supabase.

alter table public.crawl_aanvragen drop constraint crawl_aanvragen_bron_check;
alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_bron_check
  check (bron in ('visa-the-netherlands', 'caribbean-visa', 'making-appointment'));
