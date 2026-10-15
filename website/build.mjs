import { mkdir, copyFile, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(root, 'dist');
await mkdir(path.join(output, 'media'), { recursive: true });
for (const file of ['style.css', 'theme.js', 'app.js', 'icon.svg', 'inter.woff2', 'inter-LICENSE.txt']) {
  await copyFile(path.join(root, file), path.join(output, file));
}
let html = await readFile(path.join(root, 'index.html'), 'utf8');
// Resolve the current published release at build time, including early releases.
// Keep the known working download links if GitHub is temporarily unavailable.
try {
  const response = await fetch('https://api.github.com/repos/HariTP/browser-selector/releases', {
    headers: { 'User-Agent': 'browser-selector-website' }, signal: AbortSignal.timeout(10000)
  });
  if (!response.ok) throw new Error(`GitHub returned ${response.status}`);
  const releases = await response.json();
  const release = releases.find(item => !item.draft && item.assets.length > 0);
  if (release) {
    html = html.replace(/data-asset="([^"]+)" href="[^"]+"/g, (original, suffix) => {
      const asset = release.assets.find(item => item.name.endsWith(suffix));
      return asset ? `data-asset="${suffix}" href="${asset.browser_download_url}"` : original;
    });
    html = html.replace(/data-version>[^<]+</, `data-version>${release.tag_name}<`);
    console.log(`Download links: ${release.tag_name}`);
  }
} catch (error) { console.warn(`Using fallback download links: ${error.message}`); }
await writeFile(path.join(output, 'index.html'), html);
for (const file of ['demo.mp4', 'demo-poster.png']) {
  await copyFile(path.join(root, '../docs/media', file), path.join(output, 'media', file));
}
await writeFile(path.join(output, 'robots.txt'), 'User-agent: *\nAllow: /\nSitemap: https://browser-selector.haritp.dev/sitemap.xml\n');
await writeFile(path.join(output, 'sitemap.xml'), '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://browser-selector.haritp.dev/</loc></url></urlset>\n');
console.log(`Built static product page: ${output}`);
