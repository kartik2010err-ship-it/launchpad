import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Search-engine files that depend on the public domain.
 *
 * Set VITE_SITE_URL (e.g. https://researchcoach.app) in the hosting
 * environment once a custom domain is live. With it the build emits a
 * canonical link, og:url, and a sitemap; without it (preview deployments, the
 * vercel.app address) it emits a robots.txt that still allows crawling of the
 * public pages but makes no claims about which host is canonical.
 */
function siteFiles(siteUrl: string | undefined): Plugin {
  const site = siteUrl?.replace(/\/$/, "");
  return {
    name: "research-coach-site-files",
    transformIndexHtml(html) {
      if (!site) return html;
      return html.replace(
        "</head>",
        `    <link rel="canonical" href="${site}/" />\n    <meta property="og:url" content="${site}/" />\n  </head>`,
      );
    },
    generateBundle() {
      // Only the public pages are worth indexing; everything else needs a
      // sign-in and would show a crawler the sign-in form.
      // Assets stay crawlable: Google renders the landing page with its JS/CSS.
      const robots = ["User-agent: *", "Allow: /$", "Allow: /sign-in", "Allow: /assets/", "Allow: /favicon.svg", "Disallow: /"];
      if (site) robots.push(`Sitemap: ${site}/sitemap.xml`);
      this.emitFile({ type: "asset", fileName: "robots.txt", source: robots.join("\n") + "\n" });
      if (site) {
        const urls = ["/", "/sign-in"]
          .map((path) => `  <url><loc>${site}${path}</loc></url>`)
          .join("\n");
        this.emitFile({
          type: "asset",
          fileName: "sitemap.xml",
          source: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
        });
      }
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    plugins: [react(), siteFiles(env.VITE_SITE_URL || process.env.VITE_SITE_URL)],
    server: {
      port: 5173,
      proxy: {
        // Everything the API owns. Keeps the dev origin identical to production.
        "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      },
    },
  };
});
