// Convert the original photos (big JPEG/PNG files, kept OUT of git) into small WebP files for the site.
//
//   npm run images            convert new or changed originals
//   npm run images -- --force convert everything again (e.g. after changing the settings below)
//
// image-originals/site/*      → public/images/site/*.webp      (hero: max 2400px wide, others: 1200px)
// image-originals/products/*  → public/images/products/*.webp  (4:5 portrait, max 1200×1500)
//
// Product photos are named {product-slug}-{color-slug} or {product-slug}-lifestyle:
//   - colour photos are PADDED to 4:5 (never cropped, so sleeves and hems stay in the picture),
//     using the colour sampled from the edge being extended so the new strip blends in;
//   - lifestyle photos are centre-CROPPED to 4:5 (a scene can lose a little at the edges).
//
// A file is skipped when its .webp already exists and is newer than the original.
// Every run rewrites backend/seed/image-manifest.json from ALL the product .webp files, so the
// manifest is complete even when nothing was converted. `flask images sync` reads it.

import { mkdir, readdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ORIGINALS = path.resolve(FRONTEND, "../image-originals");
const OUTPUT = path.join(FRONTEND, "public/images");
const MANIFEST = path.resolve(FRONTEND, "../backend/seed/image-manifest.json");

const QUALITY = 80;
const DEFAULT_MAX_WIDTH = 1200;
const MAX_WIDTH = { hero: 2400 }; // per base name; the hero fills wide screens
const PRODUCT_RATIO = 4 / 5; // width / height of every product photo
const EDGE_BAND = 6; // px of each edge averaged to pick the padding colour
const FLATTEN_ON = "#f7f3ec"; // transparent PNGs are placed on the site background first
const INPUT_TYPES = new Set([".jpg", ".jpeg", ".png"]);
const FOLDERS = ["site", "products"];

const force = process.argv.includes("--force");

function kb(bytes) {
  return `${(bytes / 1024).toFixed(0).padStart(6)} KB`;
}

async function isUpToDate(source, target) {
  try {
    const [src, out] = await Promise.all([stat(source), stat(target)]);
    return out.mtimeMs >= src.mtimeMs;
  } catch {
    return false; // no output yet
  }
}

// --- product photos ---------------------------------------------------------------------------

/** Average colour of a strip of the image: the colour we extend that edge with. */
async function edgeColor(raw, info, region) {
  // Cut the strip out into its own image first: .stats() measures the INPUT image and ignores
  // an .extract() in the same pipeline, which would give the average of the whole photo.
  const strip = await sharp(raw, { raw: info }).extract(region).raw().toBuffer({ resolveWithObject: true });
  const { channels } = await sharp(strip.data, { raw: strip.info }).stats();
  const [r, g, b] = channels.map((channel) => Math.round(channel.mean));
  return { r, g, b };
}

/** Extend one side of a raw image with a solid colour. Raw in, raw out: no quality lost between steps. */
async function extend(raw, info, side, pixels, background) {
  const result = await sharp(raw, { raw: info })
    .extend({ top: 0, bottom: 0, left: 0, right: 0, [side]: pixels, background })
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { raw: result.data, info: result.info };
}

/**
 * Make a photo exactly 4:5 without losing any of it: add matching background strips on the
 * two sides that are too short. A square photo gets strips at the top and bottom.
 */
async function padToProductRatio(source) {
  let { data: raw, info } = await sharp(source)
    .rotate() // respect the camera's orientation tag before it's stripped
    .flatten({ background: FLATTEN_ON })
    .raw()
    .toBuffer({ resolveWithObject: true });
  const { width, height } = info;
  const note = { padded: "" };

  if (width / height > PRODUCT_RATIO) {
    // Too wide: add rows at the top and bottom.
    const extra = Math.round(width / PRODUCT_RATIO) - height;
    const band = Math.min(EDGE_BAND, height);
    const top = await edgeColor(raw, info, { left: 0, top: 0, width, height: band });
    const bottom = await edgeColor(raw, info, { left: 0, top: height - band, width, height: band });
    ({ raw, info } = await extend(raw, info, "top", Math.floor(extra / 2), top));
    ({ raw, info } = await extend(raw, info, "bottom", Math.ceil(extra / 2), bottom));
    note.padded = `padded ${extra}px top+bottom`;
  } else if (width / height < PRODUCT_RATIO) {
    // Too tall: add columns on the left and right.
    const extra = Math.round(height * PRODUCT_RATIO) - width;
    const band = Math.min(EDGE_BAND, width);
    const left = await edgeColor(raw, info, { left: 0, top: 0, width: band, height });
    const right = await edgeColor(raw, info, { left: width - band, top: 0, width: band, height });
    ({ raw, info } = await extend(raw, info, "left", Math.floor(extra / 2), left));
    ({ raw, info } = await extend(raw, info, "right", Math.ceil(extra / 2), right));
    note.padded = `padded ${extra}px left+right`;
  }
  return { image: sharp(raw, { raw: info }), width: info.width, note: note.padded };
}

async function convertProduct(source, target, base) {
  const isLifestyle = base.endsWith("-lifestyle");
  let image;
  let sourceWidth;
  let note = "";
  if (isLifestyle) {
    image = sharp(source).rotate().flatten({ background: FLATTEN_ON });
    sourceWidth = (await image.metadata()).width;
    note = "centre-cropped";
  } else {
    ({ image, width: sourceWidth, note } = await padToProductRatio(source));
  }
  const width = Math.min(DEFAULT_MAX_WIDTH, sourceWidth); // never upscale small images
  const height = Math.round(width / PRODUCT_RATIO);
  // After padding the ratio is already 4:5, so "cover" trims at most a rounding pixel there.
  // For lifestyle photos it is the centre crop.
  const info = await image
    .resize({ width, height, fit: "cover", position: "centre" })
    .webp({ quality: QUALITY, effort: 6 })
    .toFile(target);
  return { info, note };
}

// --- site photos ------------------------------------------------------------------------------

async function convertSite(source, target, base) {
  const info = await sharp(source)
    .rotate()
    .resize({ width: MAX_WIDTH[base] ?? DEFAULT_MAX_WIDTH, withoutEnlargement: true })
    .webp({ quality: QUALITY, effort: 6 }) // effort 6: slower to encode, smaller files
    .toFile(target);
  return { info, note: "" };
}

// --- folders ----------------------------------------------------------------------------------

async function convertFolder(folder) {
  const inputDir = path.join(ORIGINALS, folder);
  const outputDir = path.join(OUTPUT, folder);
  const totals = { converted: 0, skipped: 0, before: 0, after: 0 };
  let names;
  try {
    names = (await readdir(inputDir)).filter((name) => INPUT_TYPES.has(path.extname(name).toLowerCase())).sort();
  } catch {
    console.log(`- ${path.relative(FRONTEND, inputDir)} not found, skipping`);
    return totals;
  }
  await mkdir(outputDir, { recursive: true });
  console.log(`\n${folder}/`);

  for (const name of names) {
    const base = path.parse(name).name; // hero.jpeg → hero
    const source = path.join(inputDir, name);
    const target = path.join(outputDir, `${base}.webp`);

    if (!force && (await isUpToDate(source, target))) {
      totals.skipped += 1;
      console.log(`  skip     ${name} (unchanged)`);
      continue;
    }

    const convert = folder === "products" ? convertProduct : convertSite;
    const { info, note } = await convert(source, target, base);

    const before = (await stat(source)).size;
    totals.converted += 1;
    totals.before += before;
    totals.after += info.size;
    const saved = Math.round((1 - info.size / before) * 100);
    console.log(
      `  convert  ${name.padEnd(38)} ${kb(before)} → ${kb(info.size)}  (${info.width}×${info.height}, −${saved}%)` +
        (note ? `  ${note}` : ""),
    );
  }
  return totals;
}

/** List every optimized product photo for the backend. Sorted and timestamp-free, so git diffs stay small. */
async function writeManifest() {
  const dir = path.join(OUTPUT, "products");
  let files = [];
  try {
    files = (await readdir(dir)).filter((name) => name.endsWith(".webp")).sort();
  } catch {
    // no product photos yet: write an empty manifest
  }
  const images = [];
  for (const file of files) {
    const { width, height } = await sharp(path.join(dir, file)).metadata();
    images.push({ name: path.parse(file).name, url: `/images/products/${file}`, width, height });
  }
  const json =
    JSON.stringify(
      { generated_by: "frontend/scripts/optimize-images.mjs (npm run images). Do not edit by hand.", images },
      null,
      2,
    ) + "\n";
  const previous = await readFile(MANIFEST, "utf8").catch(() => "");
  if (json !== previous) await writeFile(MANIFEST, json);
  console.log(
    `\nManifest: ${path.relative(path.resolve(FRONTEND, ".."), MANIFEST)} lists ${images.length} product image(s)` +
      (json === previous ? " (unchanged)." : " (updated)."),
  );
}

const all = { converted: 0, skipped: 0, before: 0, after: 0 };
for (const folder of FOLDERS) {
  const result = await convertFolder(folder);
  for (const key of Object.keys(all)) all[key] += result[key];
}
console.log(
  `\nConverted ${all.converted}, skipped ${all.skipped}.` +
    (all.converted ? ` Total ${kb(all.before).trim()} → ${kb(all.after).trim()}.` : ""),
);
await writeManifest();
console.log("Next: cd backend && flask images sync");
