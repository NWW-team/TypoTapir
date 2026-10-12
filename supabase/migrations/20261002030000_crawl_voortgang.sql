-- Voortgang van een crawl, zodat het scherm een balk kan tonen.
--
-- De crawler (op de GitHub-runner, met de service-role key) werkt deze velden bij.
-- De browser leest ze alleen. Een crawl die van voor deze migratie stamt, krijgt
-- status 'onbekend': daar is geen voortgang van bekend en het scherm toont niets.

alter table public.crawl_aanvragen
  add column status           text not null default 'aangevraagd',
  add column paginas_klaar    integer,
  add column paginas_totaal   integer,
  add column crawl_gestart_op timestamptz,
  add column bijgewerkt_op    timestamptz,
  add column run_url          text;

update public.crawl_aanvragen set status = 'onbekend';

alter table public.crawl_aanvragen
  add constraint crawl_aanvragen_status_check
  check (status in ('aangevraagd', 'crawlen', 'publiceren', 'klaar', 'mislukt', 'onbekend'));

-- Een mislukte crawl mag de dag niet verbranden: die telt niet mee voor "één per dag".
drop index public.crawl_aanvragen_per_dag;
create unique index crawl_aanvragen_per_dag
  on public.crawl_aanvragen (((aangevraagd_op at time zone 'Europe/Amsterdam')::date))
  where status <> 'mislukt';
