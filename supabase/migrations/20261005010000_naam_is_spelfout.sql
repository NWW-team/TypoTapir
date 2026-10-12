-- Een naam die de redactie als verkeerd gespeld aanwijst, hoort bij de spelfouten in plaats van
-- bij de namen. Dit is bewust een eigen tabel naast `goedgekeurd`: een foute naam mag nooit per
-- ongeluk als goed tellen.
--
-- Zoals bij `goedgekeurd` mag de browser lezen maar niet schrijven; schrijven gaat via de Edge
-- Function `naam-verplaatsen`. Terugzetten verwijdert niets: het zet `teruggezet_op`.

create table public.naam_is_spelfout (
  id            bigint generated always as identity primary key,
  woord         text not null check (char_length(woord) between 1 and 100),
  verplaatst_op timestamptz not null default now(),
  teruggezet_op timestamptz
);

create unique index naam_is_spelfout_actief
  on public.naam_is_spelfout (lower(woord)) where teruggezet_op is null;

alter table public.naam_is_spelfout enable row level security;

create policy "lezen voor iedereen" on public.naam_is_spelfout
  for select to anon, authenticated using (true);

-- Een nieuwe tabel krijgt standaard alle rechten; alleen lezen is nodig (zie 20261002040000_rechten.sql).
revoke insert, update, delete, truncate, references, trigger
  on public.naam_is_spelfout from anon, authenticated;
