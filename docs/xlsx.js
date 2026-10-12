// Maakt een Excel-bestand (.xlsx) in de browser, zonder bibliotheek en zonder server.
//
// Een .xlsx is een zipbestand met een paar XML-bestanden. Dit schrijft het kleinste dat Excel,
// LibreOffice en Numbers goed openen: één werkblad met een vette kopregel, vaste kolombreedtes,
// een bevroren kopregel en filterknoppen. Tekst gaat als "inline string", dus nooit als formule:
// een woord dat met = + - of @ begint, blijft gewoon tekst.
//
//   const bytes = maakXlsx({
//     werkblad: "Spelfouten",
//     kolommen: [{ titel: "Woord", breedte: 24 }, { titel: "Zin", breedte: 80 }],
//     rijen: [["nieet", "Dat is nieet goed."]],
//   });                                  // Uint8Array
//
// Een cel mag ook een lijst met stukken zijn, om een deel van de tekst vet te maken:
//   ["Dat is ", { tekst: "nieet", vet: true }, " goed."]
//
// De tests staan in scripts/test.py (die dit bestand onder Node laadt).

(function (wereld) {
  "use strict";

  const encoder = new TextEncoder();

  // --- CRC-32, zoals de zipindeling dat eist ---------------------------------------------
  const CRC_TABEL = (() => {
    const tabel = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      tabel[n] = c >>> 0;
    }
    return tabel;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABEL[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  // --- Een zipbestand zonder compressie ("stored") ---------------------------------------
  function zip(bestanden) {
    const delen = [];
    const centraal = [];
    let positie = 0;

    const u16 = (v) => [v & 0xff, (v >>> 8) & 0xff];
    const u32 = (v) => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
    // Vaste datum (1 januari 1980): het bestand hoeft geen tijdstempel te dragen.
    const TIJD = 0, DATUM = 0x21;

    for (const { naam, inhoud } of bestanden) {
      const naamBytes = encoder.encode(naam);
      const data = typeof inhoud === "string" ? encoder.encode(inhoud) : inhoud;
      const crc = crc32(data);
      const kop = Uint8Array.from([
        ...u32(0x04034b50), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(TIJD), ...u16(DATUM),
        ...u32(crc), ...u32(data.length), ...u32(data.length), ...u16(naamBytes.length), ...u16(0),
      ]);
      delen.push(kop, naamBytes, data);
      centraal.push({ naamBytes, crc, grootte: data.length, begin: positie });
      positie += kop.length + naamBytes.length + data.length;
    }

    const centraalBegin = positie;
    for (const { naamBytes, crc, grootte, begin } of centraal) {
      const kop = Uint8Array.from([
        ...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(TIJD),
        ...u16(DATUM), ...u32(crc), ...u32(grootte), ...u32(grootte), ...u16(naamBytes.length),
        ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(begin),
      ]);
      delen.push(kop, naamBytes);
      positie += kop.length + naamBytes.length;
    }
    delen.push(Uint8Array.from([
      ...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(centraal.length), ...u16(centraal.length),
      ...u32(positie - centraalBegin), ...u32(centraalBegin), ...u16(0),
    ]));

    const uit = new Uint8Array(delen.reduce((som, d) => som + d.length, 0));
    let schuif = 0;
    for (const d of delen) { uit.set(d, schuif); schuif += d.length; }
    return uit;
  }

  // --- De XML ---------------------------------------------------------------------------
  // Tekens die in XML 1.0 niet mogen voorkomen (besturingstekens) halen we weg; de rest ontsnappen we.
  const ONGELDIG = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g;
  const ontsnap = (tekst) => String(tekst).replace(ONGELDIG, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  // A, B, ... Z, AA, AB ...
  function kolomLetter(nummer) {
    let letter = "";
    for (let n = nummer + 1; n > 0; n = Math.floor((n - 1) / 26)) {
      letter = String.fromCharCode(65 + ((n - 1) % 26)) + letter;
    }
    return letter;
  }

  // Excel laat per cel maximaal 32.767 tekens toe.
  const MAX_CEL = 32767;

  function cel(waarde, verwijzing, stijl) {
    const s = stijl ? ` s="${stijl}"` : "";
    if (waarde === null || waarde === undefined || waarde === "") return "";
    if (typeof waarde === "number" && Number.isFinite(waarde)) {
      return `<c r="${verwijzing}"${s}><v>${waarde}</v></c>`;
    }
    if (Array.isArray(waarde)) {
      // Opgemaakte tekst: een stuk per <r>. Vet krijgt zijn eigen lettertype, de rest erft van de cel.
      let over = MAX_CEL;
      const stukken = [];
      for (const stuk of waarde) {
        const gegeven = typeof stuk === "string" ? { tekst: stuk } : stuk;
        const tekst = String(gegeven.tekst ?? "").slice(0, over);
        over -= tekst.length;
        if (!tekst) continue;
        const opmaak = gegeven.vet ? '<rPr><rFont val="Calibri"/><b/><sz val="11"/></rPr>' : "";
        stukken.push(`<r>${opmaak}<t xml:space="preserve">${ontsnap(tekst)}</t></r>`);
      }
      if (!stukken.length) return "";
      return `<c r="${verwijzing}"${s} t="inlineStr"><is>${stukken.join("")}</is></c>`;
    }
    const tekst = ontsnap(String(waarde).slice(0, MAX_CEL));
    return `<c r="${verwijzing}"${s} t="inlineStr"><is><t xml:space="preserve">${tekst}</t></is></c>`;
  }

  function werkbladXml(kolommen, rijen) {
    const laatsteKolom = kolomLetter(kolommen.length - 1);
    const laatsteRij = rijen.length + 1;
    const breedtes = kolommen.map((k, i) =>
      `<col min="${i + 1}" max="${i + 1}" width="${k.breedte || 20}" customWidth="1"/>`).join("");
    const kop = kolommen.map((k, i) => cel(k.titel, `${kolomLetter(i)}1`, 1)).join("");
    const lichaam = rijen.map((rij, r) =>
      `<row r="${r + 2}">${rij.map((w, i) => cel(w, `${kolomLetter(i)}${r + 2}`, 2)).join("")}</row>`).join("");
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<cols>${breedtes}</cols>
<sheetData><row r="1">${kop}</row>${lichaam}</sheetData>
<autoFilter ref="A1:${laatsteKolom}${laatsteRij}"/>
</worksheet>`;
  }

  // Stijl 0 = standaard, 1 = vet (kopregel), 2 = tekst die mag doorlopen naar een volgende regel.
  const STIJLEN = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
</cellXfs>
</styleSheet>`;

  // Een werkbladnaam mag niet langer zijn dan 31 tekens en geen : \ / ? * [ ] bevatten.
  const werkbladNaam = (naam) => String(naam).replace(/[:\\/?*\[\]]/g, " ").trim().slice(0, 31).trim() || "Blad1";

  function maakXlsx({ werkblad, kolommen, rijen }) {
    return zip([
      { naam: "[Content_Types].xml", inhoud: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>` },
      { naam: "_rels/.rels", inhoud: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>` },
      { naam: "xl/workbook.xml", inhoud: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="${ontsnap(werkbladNaam(werkblad))}" sheetId="1" r:id="rId1"/></sheets>
</workbook>` },
      { naam: "xl/_rels/workbook.xml.rels", inhoud: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>` },
      { naam: "xl/styles.xml", inhoud: STIJLEN },
      { naam: "xl/worksheets/sheet1.xml", inhoud: werkbladXml(kolommen, rijen) },
    ]);
  }

  // Zet de bytes als bestand klaar om te downloaden.
  function downloadXlsx(bestandsnaam, gegevens) {
    const blob = new Blob([maakXlsx(gegevens)], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = bestandsnaam;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  wereld.maakXlsx = maakXlsx;
  wereld.downloadXlsx = downloadXlsx;
  if (typeof module !== "undefined" && module.exports) module.exports = { maakXlsx, crc32, kolomLetter };
})(typeof window !== "undefined" ? window : globalThis);
