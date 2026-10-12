-- De delen van de site die je kunt kiezen: reisadvies, visum-nederland, caribisch-visum en
-- ambassades. "paginas" (alle overige pagina's) is geen keuze meer. Een deel is een pad in
-- scripts/crawl.py (DELEN); alles daarachter hoort erbij. Al toegepast in Supabase.

alter table public.crawl_aanvragen drop constraint crawl_aanvragen_bron_check;
alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_bron_check
  check (bron in ('reisadvies', 'visum-nederland', 'caribisch-visum', 'ambassades'));
