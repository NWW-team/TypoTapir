-- Een crawl stoppen: de aanvraag kan op 'gestopt' staan, en een gestopte crawl telt (net als een
-- mislukte) niet mee voor "één per dag".
--
-- Het statusdeel is al toegepast in Supabase. De unieke index (laatste twee statements)
-- niet: een DROP INDEX loopt via de MCP-koppeling steeds vast en moet in de SQL Editor van het
-- dashboard worden gedraaid. Dit vervangt ook de index uit 20261002030000_crawl_voortgang.sql.

alter table public.crawl_aanvragen drop constraint crawl_aanvragen_status_check;
alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_status_check
  check (status in ('aangevraagd', 'crawlen', 'publiceren', 'klaar', 'mislukt', 'gestopt', 'onbekend'));

drop index public.crawl_aanvragen_per_dag;
create unique index crawl_aanvragen_per_dag
  on public.crawl_aanvragen (((aangevraagd_op at time zone 'Europe/Amsterdam')::date))
  where status not in ('mislukt', 'gestopt');
