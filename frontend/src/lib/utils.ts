import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function slugifyVi(input: string, maxWords = 8): string {
  const words = input
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s-]/g, " ")
    .trim()
    .split(/\s+/)
    .slice(0, maxWords);
  const slug = words.join("-").replace(/-+/g, "-");
  return slug || "chu-de";
}

export function shortId(length = 11): string {
  const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let out = "";
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  for (let i = 0; i < length; i++) {
    out += alphabet[array[i] % alphabet.length];
  }
  return out;
}

// Normalize links in text to markdown format where the anchor is a one-word site name
// Examples:
//   "[loigiaihay.com](https://loigiaihay.com/x)" -> "[loigiaihay](https://loigiaihay.com/x)"
//   "See https://example.co.uk/abc" -> "See [example](https://example.co.uk/abc)"
export function normalizeLinksToSiteAnchors(text: string): string {
  if (!text || typeof text !== "string") return text;

  // Skip simple fenced code blocks by splitting on ``` and only transforming non-code segments
  const segments = text.split(/```/);

  for (let i = 0; i < segments.length; i += 2) {
    let segment = segments[i];

    // 1) Replace existing markdown links' labels with site name
    segment = segment.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gi, (_m, _label: string, url: string) => {
      const site = extractSiteNameFromUrl(url);
      return `[${site}](${url})`;
    });

    // 2) Convert bare URLs not already part of markdown into [site](url)
    // Require preceding char to be whitespace or common punctuation (not '(') so we don't touch "](<url>)" cases
    segment = segment.replace(/(^|[\s\t\n\r\f\v\u00A0.,;:!?"'`~_\-–—\[\{<])((https?:\/\/[^\s<>\)"']+))/gi, (_m, prefix: string, url: string) => {
      const site = extractSiteNameFromUrl(url);
      return `${prefix}[${site}](${url})`;
    });

    segments[i] = segment;
  }

  return segments.join("```");
}

function extractSiteNameFromUrl(urlStr: string): string {
  try {
    const u = new URL(urlStr);
    let host = u.hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);

    const parts = host.split(".").filter(Boolean);
    if (parts.length === 0) return host.replace(/\./g, "");

    const multiTld = new Set([
      "co.uk",
      "com.au",
      "co.jp",
      "com.vn",
      "gov.vn",
      "org.vn",
      "net.cn",
      "com.cn",
    ]);

    let base = "";
    if (parts.length >= 3) {
      const lastTwo = `${parts[parts.length - 2]}.${parts[parts.length - 1]}`;
      if (multiTld.has(lastTwo) && parts.length >= 3) {
        base = parts[parts.length - 3];
      } else {
        base = parts[parts.length - 2];
      }
    } else if (parts.length >= 2) {
      base = parts[parts.length - 2];
    } else {
      base = parts[0];
    }

    // Keep alphanumerics only to ensure a single word
    const cleaned = base.replace(/[^a-z0-9]/gi, "");
    return cleaned || host.replace(/\./g, "");
  } catch {
    // Fallback for invalid URLs
    return "link";
  }
}

// Produce a stable key for matching URLs coming from different sources (LLM output vs search results)
// - lowercases host
// - strips leading www.
// - removes query and hash
// - removes trailing slash (except on root)
// - decodes percent-encoded path to unify forms
export function normalizeUrlForMatch(urlStr: string): string {
  try {
    const u = new URL(urlStr);
    let host = u.hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);
    let pathname = u.pathname || "/";
    try {
      pathname = decodeURIComponent(pathname);
    } catch {
      // ignore decode errors
    }
    if (pathname.length > 1 && pathname.endsWith("/")) {
      pathname = pathname.slice(0, -1);
    }
    return `${u.protocol}//${host}${pathname}`;
  } catch {
    return urlStr;
  }
}

// Remove HTML tags and normalize whitespace. Also decode a few common entities.
export function stripHtml(input: string | undefined | null): string {
  if (!input) return "";
  let out = String(input)
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'");
  out = out.replace(/\s+/g, " ").trim();
  return out;
}

// Shared upload limits and helpers (used by translate and prompt input)
export const MAX_UPLOAD_FILE_BYTES = 5 * 1024 * 1024; // 5 MB

export function exceedsFileLimit(file: File, limitBytes: number = MAX_UPLOAD_FILE_BYTES): boolean {
  return file.size > limitBytes;
}

export function formatMb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}
