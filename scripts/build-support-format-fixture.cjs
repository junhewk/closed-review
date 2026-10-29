#!/usr/bin/env node
// Local format fixture only: no clinical judgments, model calls or private evaluator keys.
// Requires docx in the caller's Node module path; it is NOT a runtime plugin dependency.
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, WidthType, ShadingType,
} = require("docx");

const sources = {
  case02: { file: "evals/support-pilot/manuscripts/case-02.md", tables: 1 },
  r17: { file: "evals/support-ordinary-draft/manuscripts/r17.md", tables: 3 },
};
const output = process.argv[2];
const fixture = process.argv[3] || "case02";
if (![3, 4].includes(process.argv.length) || !Object.hasOwn(sources, fixture)
    || !output || fs.existsSync(output)) {
  throw new Error("Usage: build-support-format-fixture.cjs NEW_OUTPUT_DIRECTORY [case02|r17]");
}
const source = path.resolve(__dirname, "..", sources[fixture].file);
const sourceBytes = fs.readFileSync(source);
const original = sourceBytes.toString("utf8");
const lines = original.split(/\r?\n/);
const children = [];
const paragraphs = [];
const tableValues = [];
const contentWidth = 10080;
let pending = [];

function addParagraph(value, heading) {
  paragraphs.push(value);
  children.push(new Paragraph({
    children: [new TextRun({ text: value })],
    ...(heading ? { heading } : {}),
    keepNext: Boolean(heading),
    spacing: { before: heading ? 140 : 0, after: 100 },
  }));
}

function flushParagraph() {
  if (pending.length) addParagraph(pending.join(" "));
  pending = [];
}

function splitRow(value) {
  if (!value.trim().startsWith("|") || !value.trim().endsWith("|")) {
    throw new Error("This fixed fixture generator accepts only simple pipe tables");
  }
  return value.trim().slice(1, -1).split("|").map(cell => cell.trim());
}

for (let index = 0; index < lines.length; index += 1) {
  const line = lines[index];
  if (!line.trim()) { flushParagraph(); continue; }
  const heading = line.match(/^(#{1,3}) (.+)$/);
  if (heading) {
    flushParagraph();
    addParagraph(heading[2], [HeadingLevel.TITLE, HeadingLevel.HEADING_1,
      HeadingLevel.HEADING_2][heading[1].length - 1]);
    continue;
  }
  if (line.startsWith("|")) {
    flushParagraph();
    const rows = [];
    while (index < lines.length && lines[index].startsWith("|")) {
      rows.push(splitRow(lines[index])); index += 1;
    }
    index -= 1;
    if (rows.length < 3 || !rows[1].every(cell => /^:?-+:?$/.test(cell))) {
      throw new Error("Expected one ordinary Markdown header separator");
    }
    rows.splice(1, 1);
    const count = rows[0].length;
    if (!rows.every(row => row.length === count)) throw new Error("Unexpected ragged source");
    const widths = Array(count).fill(Math.floor(contentWidth / count));
    widths[count - 1] += contentWidth - widths.reduce((sum, value) => sum + value, 0);
    tableValues.push(rows);
    children.push(new Table({
      width: { size: contentWidth, type: WidthType.DXA },
      columnWidths: widths,
      rows: rows.map((row, rowIndex) => new TableRow({
        tableHeader: rowIndex === 0,
        cantSplit: true,
        children: row.map((cell, column) => new TableCell({
          width: { size: widths[column], type: WidthType.DXA },
          ...(rowIndex === 0 ? { shading: { type: ShadingType.CLEAR, fill: "EEF1F4" } } : {}),
          children: [new Paragraph({
            children: [new TextRun({ text: cell, bold: rowIndex === 0 })],
            spacing: { before: 40, after: 40 },
            keepNext: rowIndex < rows.length - 1,
          })],
        })),
      })),
    }));
    continue;
  }
  pending.push(line);
}
flushParagraph();
if (tableValues.length !== sources[fixture].tables) {
  throw new Error("Unexpected table count in the fixed synthetic source");
}
const document = new Document({
  creator: "closed-review synthetic format fixture",
  title: "Synthetic manuscript format-equivalence fixture",
  description: "Invented engineering input; not a validated medical control",
  styles: { default: { document: { run: { font: "Liberation Sans", size: 22 } } } },
  sections: [{
    properties: { page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 },
    } },
    children,
  }],
});

async function main() {
  const buffer = await Packer.toBuffer(document);
  if (!fs.readFileSync(source).equals(sourceBytes)) throw new Error("Source changed during build");
  fs.mkdirSync(output, { recursive: false, mode: 0o700 });
  fs.writeFileSync(path.join(output, "f01.docx"), buffer, { flag: "wx", mode: 0o600 });
  fs.copyFileSync(source, path.join(output, "f00.md"), fs.constants.COPYFILE_EXCL);
  fs.chmodSync(path.join(output, "f00.md"), 0o600);
  const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
  const provenance = {
    synthetic_only: true,
    independently_reviewed: false,
    fixture,
    source: sources[fixture].file,
    source_sha256: hash(sourceBytes),
    generator_sha256: hash(fs.readFileSync(__filename)),
    docx_sha256: hash(buffer),
    node_version: process.version,
    paragraphs,
    tables: tableValues,
    note: "Same invented content in native formats; not independent studies or quality labels.",
  };
  fs.writeFileSync(path.join(output, "build.json"), JSON.stringify(provenance, null, 2) + "\n",
    { flag: "wx", mode: 0o600 });
  process.stdout.write(JSON.stringify({ directory: path.resolve(output),
    docx_sha256: provenance.docx_sha256, source_sha256: provenance.source_sha256 }) + "\n");
}
main().catch(error => { process.stderr.write(error.message + "\n"); process.exitCode = 1; });
