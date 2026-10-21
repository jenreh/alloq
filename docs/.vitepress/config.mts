import { posix } from "node:path";
import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";

const REPO_URL = "https://github.com/jenreh/alloq";
const EXTERNAL_RE = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

/**
 * Resolves a relative link against the page directory. Returns the path
 * relative to the repository root when the link leaves docs/, else null.
 */
function repoPathOutsideDocs(
  href: string,
  relativePath: string,
): { path: string; suffix: string } | null {
  if (!href || href.startsWith("#") || href.startsWith("/")) return null;
  if (EXTERNAL_RE.test(href)) return null;
  const cut = href.search(/[?#]/);
  const target = cut >= 0 ? href.slice(0, cut) : href;
  const suffix = cut >= 0 ? href.slice(cut) : "";
  const resolved = posix.normalize(
    posix.join(posix.dirname(relativePath || "index.md"), target),
  );
  if (!resolved.startsWith("../")) return null;
  return { path: resolved.slice(3), suffix };
}

function githubUrl(path: string, suffix: string): string {
  const last = path.replace(/\/$/, "").split("/").pop() ?? "";
  const isFolder = path.endsWith("/") || !last.includes(".");
  const kind = isFolder ? "tree" : "blob";
  return `${REPO_URL}/${kind}/main/${path.replace(/\/$/, "")}${suffix}`;
}

export default withMermaid(
  defineConfig({
    title: "Alloq",
    description:
      "Developer documentation for Alloq, the resource and capacity planning app for software teams.",
    srcExclude: [".work/**", "**/node_modules/**"],
    cleanUrls: false,
    lastUpdated: false,
    markdown: {
      config: (md) => {
        md.core.ruler.push("alloq_source_links", (state) => {
          const relativePath: string = state.env?.relativePath ?? "";
          for (const block of state.tokens) {
            if (block.type !== "inline" || !block.children) continue;
            for (const token of block.children) {
              if (token.type !== "link_open") continue;
              const href = token.attrGet("href") ?? "";
              const repo = repoPathOutsideDocs(href, relativePath);
              if (!repo) continue;
              token.attrSet("href", githubUrl(repo.path, repo.suffix));
              token.attrSet("target", "_blank");
              token.attrSet("rel", "noopener");
            }
          }
        });
      },
    },
    vite: {
      optimizeDeps: {
        include: ["mermaid", "fastdom"],
      },
    },
    themeConfig: {
      nav: [
        { text: "Guide", link: "/guide/getting-started" },
        { text: "Architecture", link: "/architecture/overview" },
        { text: "Features", link: "/features/story-map" },
        { text: "Reference", link: "/reference/commands" },
      ],
      sidebar: [
        {
          text: "Guide",
          items: [
            { text: "Getting started", link: "/guide/getting-started" },
            { text: "Contributing", link: "/guide/contributing" },
          ],
        },
        {
          text: "Architecture",
          items: [
            { text: "Architecture overview", link: "/architecture/overview" },
            { text: "Layers", link: "/architecture/layers" },
            { text: "Data model", link: "/architecture/data-model" },
            {
              text: "Security and access",
              link: "/architecture/security-and-access",
            },
            { text: "Calculations", link: "/architecture/calculations" },
            { text: "Desktop app", link: "/architecture/desktop" },
          ],
        },
        {
          text: "Features",
          items: [
            { text: "Story map", link: "/features/story-map" },
            { text: "Sign in and find your way", link: "/features/sign-in" },
            { text: "Users and access", link: "/features/users-and-access" },
            {
              text: "Roles, rates, departments and holidays",
              link: "/features/master-data",
            },
            { text: "Team", link: "/features/team" },
            { text: "Offers", link: "/features/offers" },
            { text: "Find and create projects", link: "/features/projects" },
            {
              text: "Maintain and track a project",
              link: "/features/project-tracking",
            },
            { text: "Planning grid", link: "/features/planning-grid" },
            {
              text: "Planning filters and view",
              link: "/features/planning-view",
            },
            { text: "Staff a project", link: "/features/staffing" },
            { text: "Absences and availability", link: "/features/absences" },
            { text: "Portfolio overview", link: "/features/portfolio" },
            {
              text: "Portfolio staffing and capacity",
              link: "/features/portfolio-capacity",
            },
            { text: "Desktop app", link: "/features/desktop" },
          ],
        },
        {
          text: "Reference",
          items: [
            { text: "Commands", link: "/reference/commands" },
            { text: "Configuration", link: "/reference/configuration" },
            { text: "Testing", link: "/reference/testing" },
            { text: "Glossary", link: "/reference/glossary" },
          ],
        },
      ],
      search: { provider: "local" },
      outline: [2, 3],
      socialLinks: [{ icon: "github", link: REPO_URL }],
    },
  }),
);
