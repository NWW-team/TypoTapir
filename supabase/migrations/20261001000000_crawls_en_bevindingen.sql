-- De basis: de tabellen met de crawlresultaten.
--
-- In het Nederlandse origineel (SpellingSpeurneus) zijn deze twee tabellen met de hand aangemaakt
-- en stond dat niet in een migratie. Voor een nieuw project is dat wel nodig: alle latere migraties
-- gaan ervan uit dat ze bestaan. Dit is de vorm die het origineel had op 12 oktober 2026, zonder de
-- kolommen die latere migraties toevoegen (plaats_status en suggestie, in 20261002060000).
--
-- Schrijven kan alleen de service-role key (de workflow). RLS en de leesrechten voor het scherm staan
-- in 20261002000000_open_lezen.sql en 20261002040000_rechten.sql.

create table public.crawls (
  id                uuid primary key default gen_random_uuid(),
  gestart_op        timestamptz not null,
  bron              text not null,
  woordenlijst      text,
  user_agent        text,
  aantal_paginas    integer,
  overgeslagen_urls jsonb not null default '[]'::jsonb,
  aangemaakt_op     timestamptz not null default now()
);

create table public.bevindingen (
  id       bigint generated always as identity primary key,
  crawl_id uuid not null references public.crawls (id) on delete cascade,
  url      text not null,
  titel    text,
  woord    text not null,
  soort    text not null check (soort in ('spelfout', 'naam')),
  context  text
);

create index bevindingen_crawl_soort_idx on public.bevindingen (crawl_id, soort);

-- Een nieuwe tabel krijgt standaard alle rechten; de browser hoeft alleen te lezen.
revoke insert, update, delete, truncate, references, trigger
  on public.crawls, public.bevindingen from anon, authenticated;
