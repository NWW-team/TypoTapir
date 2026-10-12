-- Stap 4: een oordeel over namen, op basis van GeoNames (zie scripts/plaatsnamen.py).
--
-- plaats_status: 'bekend' (komt voor in GeoNames), 'twijfel' (komt niet voor maar lijkt
-- op een bekende plaats) of 'onbekend'. Alleen gevuld bij namen, en alleen als de
-- plaatsnamenlijst bij de crawl beschikbaar was. suggestie: de plaats waar een naam op lijkt.

alter table public.bevindingen
  add column plaats_status text,
  add column suggestie     text;

alter table public.bevindingen
  add constraint bevindingen_plaats_status_check
  check (plaats_status is null or plaats_status in ('bekend', 'twijfel', 'onbekend'));
