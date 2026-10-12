-- Stap 3: een crawl starten vanuit het scherm, één per dag.
--
-- Elke aanvraag is een rij. De unieke index op de datum (Nederlandse tijd) maakt
-- "één per dag" een regel van de database en niet van de code: twee aanvragen op
-- hetzelfde moment kunnen er niet allebei doorheen. De Edge Function `crawl-starten`
-- schrijft; de browser mag alleen lezen, zodat de knop kan tonen of er vandaag al
-- een crawl is gestart.

create table public.crawl_aanvragen (
  id             bigint generated always as identity primary key,
  aangevraagd_op timestamptz not null default now(),
  bron           text not null check (bron in ('reisadvies', 'paginas', 'ambassades')),
  max_paginas    integer not null check (max_paginas between 1 and 5000)
);

create unique index crawl_aanvragen_per_dag
  on public.crawl_aanvragen (((aangevraagd_op at time zone 'Europe/Amsterdam')::date));

alter table public.crawl_aanvragen enable row level security;

create policy "lezen voor iedereen" on public.crawl_aanvragen
  for select to anon, authenticated using (true);
-- Bewust geen insert/update/delete-policy: alleen de service-role key schrijft.
