import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = resolve(root, "data/source-manifest.json");
const outputPath = resolve(root, "data/import-candidates.generated.json");

const programmePattern = /\b(certificate|diploma|bachelor|bsc|ba|beng|bed|bcom|degree|programme|program)\b/i;

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, "\n")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function extractCandidates(text, source) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length >= 12 && line.length <= 160)
    .filter((line) => programmePattern.test(line))
    .slice(0, 30)
    .map((line, index) => ({
      id: `${source.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${index + 1}`,
      source_name: source.name,
      source_url: source.url,
      entity_type: "programme",
      title: line,
      confidence: source.kind.includes("official") ? 70 : 55,
      status: "pending",
      evidence_text: line
    }));
}

async function fetchSource(source) {
  if (source.kind.includes("pdf")) {
    return [{
      id: `${source.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-pdf`,
      source_name: source.name,
      source_url: source.url,
      entity_type: "source_document",
      title: `${source.name} PDF requires PDF text extraction`,
      confidence: 50,
      status: "pending",
      evidence_text: "PDF source queued for manual/PDF extraction."
    }];
  }

  const response = await fetch(source.url, {
    headers: {
      "User-Agent": "EduGuideLS/0.1 data review crawler"
    }
  });
  const body = await response.text();
  const text = stripHtml(body);
  return extractCandidates(text, source);
}

async function main() {
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const batches = [];

  for (const source of manifest) {
    try {
      batches.push(...await fetchSource(source));
    } catch (error) {
      batches.push({
        id: `${source.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-error`,
        source_name: source.name,
        source_url: source.url,
        entity_type: "source_error",
        title: `Fetch failed for ${source.name}`,
        confidence: 0,
        status: "error",
        evidence_text: error.message
      });
    }
  }

  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, JSON.stringify(batches, null, 2));
  console.log(`Wrote ${batches.length} import candidates to ${outputPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
