-- Stap 2: woorden en namen goedkeuren vanuit het scherm.
--
-- De browser mag deze tabel lezen maar niet schrijven. Schrijven gaat via de Edge
-- Function `goedkeuren`, die met de service-role key werkt en een limiet houdt.
-- Intrekken verwijdert niets: het zet `ingetrokken_op`, zodat de geschiedenis blijft.

create table public.goedgekeurd (
  id             bigint generated always as identity primary key,
  woord          text not null check (char_length(woord) between 1 and 100),
  soort          text not null check (soort in ('woord', 'naam')),
  goedgekeurd_op timestamptz not null default now(),
  ingetrokken_op timestamptz
);

-- Een woord kan maar één keer tegelijk actief goedgekeurd zijn, hoofdletters
-- tellen niet mee. Na intrekken mag het opnieuw: dat wordt een nieuwe rij.
create unique index goedgekeurd_actief
  on public.goedgekeurd (lower(woord), soort) where ingetrokken_op is null;

alter table public.goedgekeurd enable row level security;

create policy "lezen voor iedereen" on public.goedgekeurd
  for select to anon, authenticated using (true);
-- Bewust geen insert/update/delete-policy: alleen de service-role key schrijft.
