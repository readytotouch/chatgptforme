// Command generate builds every HTML page of the site from public/engines.json,
// locales/*.json and templates/*.html:
//   - public/index.html and public/<locale>/index.html
//   - public/<slug>/index.html and public/<locale>/<slug>/index.html per AI assistant
//   - public/sitemap-main.xml with hreflang alternates
//
// Run it from the repository root: go run ./cmd/generate
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html"
	"html/template"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type Site struct {
	Name    string `json:"name"`
	URL     string `json:"url"`
	Tagline string `json:"tagline"`
}

type Engine struct {
	Slug             string `json:"slug,omitempty"`
	Name             string `json:"name"`
	ShortName        string `json:"shortName,omitempty"`
	Vendor           string `json:"vendor,omitempty"`
	Home             string `json:"home,omitempty"`
	Icon             string `json:"icon"`
	Mono             bool   `json:"mono,omitempty"` // black logo: inverted in the dark theme
	URL              string `json:"url"`
	Signature        string `json:"signature,omitempty"`
	Prefill          string `json:"prefill,omitempty"` // yes | partial | none (AI assistants only)
	Notes            string `json:"notes,omitempty"`
	Account          string `json:"account,omitempty"`
	GoogleSitePrefix string `json:"googleSitePrefix,omitempty"`
}

func (e Engine) Short() string {
	if e.ShortName != "" {
		return e.ShortName
	}
	return e.Name
}

func (e Engine) CopyOnly() bool { return e.Prefill == "none" }

type Group struct {
	GroupName string   `json:"groupName"`
	Engines   []Engine `json:"engines"`
}

type Data struct {
	Site   Site    `json:"site"`
	Groups []Group `json:"groups"`
}

type FAQ struct {
	Q string `json:"q"`
	A string `json:"a"`
}

type EngineText struct {
	Notes   string `json:"notes"`
	Account string `json:"account"`
}

type Locale struct {
	Code     string                `json:"code"`
	HTMLLang string                `json:"htmlLang"`
	OGLocale string                `json:"ogLocale"`
	Path     string                `json:"path"` // "" for the default locale, "/uk" otherwise
	Name     string                `json:"name"`
	T        map[string]string     `json:"t"` // plain-text strings
	H        map[string]string     `json:"h"` // strings that contain markup
	FAQ      []FAQ                 `json:"faq"`
	Engines  map[string]EngineText `json:"engines"` // per-slug overrides of notes / account
}

// Alternate is one hreflang link (and one entry of the language switcher).
type Alternate struct {
	Code    string
	Name    string
	Href    string // absolute, for hreflang links
	RelHref string // site-relative, for the language switcher
	Current bool
}

type aiRow struct {
	Slug, Name, Label, Notes, Href, Icon, LinkText string
	Mono                                           bool
}

type basePage struct {
	Site              Site
	L                 *Locale
	T                 map[string]string
	H                 map[string]template.HTML
	Canonical         string
	OGImage           string
	Alternates        []Alternate
	XDefault          string
	HomeHref          string
	BookmarkletTarget string // URL prefix the bookmarklet appends the encoded selection to
	JSONLD            template.JS
	I18nJSON          template.JS
	Today             string
}

type indexPage struct {
	basePage
	FAQ        []FAQ
	AI         []aiRow
	GroupsJSON template.JS
}

type enginePage struct {
	basePage
	Engine     Engine
	Others     []aiRow
	EngineJSON template.JS
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "generate:", err)
		os.Exit(1)
	}
}

func run() error {
	data, err := loadData()
	if err != nil {
		return err
	}
	locales, err := loadLocales()
	if err != nil {
		return err
	}
	ai, err := aiEngines(data)
	if err != nil {
		return err
	}
	tmpl, err := template.ParseFiles("templates/_shared.html", "templates/index.html", "templates/engine.html")
	if err != nil {
		return err
	}
	today := sourceDate()

	generated := map[string]bool{}
	for _, loc := range locales {
		path, err := renderIndex(tmpl, data, ai, locales, loc, today)
		if err != nil {
			return err
		}
		generated[path] = true
		for _, e := range ai {
			path, err := renderEngine(tmpl, data, ai, locales, loc, e, today)
			if err != nil {
				return err
			}
			generated[path] = true
		}
	}
	if err := removeStalePages(generated); err != nil {
		return err
	}
	return writeSitemaps(data.Site, ai, locales, today)
}

// removeStalePages deletes public/**/index.html files this run did not produce
// (a removed locale or assistant) together with their now-empty directories.
func removeStalePages(generated map[string]bool) error {
	return filepath.WalkDir("public", func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() || d.Name() != "index.html" || generated[filepath.ToSlash(path)] {
			return err
		}
		if err := os.Remove(path); err != nil {
			return err
		}
		fmt.Println("removed stale", path)
		for dir := filepath.Dir(path); dir != "public"; dir = filepath.Dir(dir) {
			if os.Remove(dir) != nil { // not empty: stop climbing
				break
			}
		}
		return nil
	})
}

func loadData() (Data, error) {
	var data Data
	raw, err := os.ReadFile("public/engines.json")
	if err != nil {
		return data, err
	}
	if err := json.Unmarshal(raw, &data); err != nil {
		return data, fmt.Errorf("engines.json: %w", err)
	}
	return data, nil
}

func aiEngines(data Data) ([]Engine, error) {
	for _, g := range data.Groups {
		if g.GroupName != "AI Assistants" {
			continue
		}
		for _, e := range g.Engines {
			if e.Slug == "" || e.Prefill == "" {
				return nil, fmt.Errorf("engines.json: AI assistant %q needs slug and prefill", e.Name)
			}
		}
		return g.Engines, nil
	}
	return nil, fmt.Errorf("engines.json: no \"AI Assistants\" group")
}

// loadLocales reads locales/*.json; "en" is the default locale and comes first.
func loadLocales() ([]*Locale, error) {
	files, err := filepath.Glob("locales/*.json")
	if err != nil {
		return nil, err
	}
	var locales []*Locale
	var ref *Locale
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			return nil, err
		}
		var loc Locale
		if err := json.Unmarshal(raw, &loc); err != nil {
			return nil, fmt.Errorf("%s: %w", f, err)
		}
		if loc.Code == "en" {
			if loc.Path != "" {
				return nil, fmt.Errorf("%s: the default locale must have an empty path", f)
			}
			ref = &loc
		}
		locales = append(locales, &loc)
	}
	if ref == nil {
		return nil, fmt.Errorf("locales/en.json is required")
	}
	for _, loc := range locales {
		for key := range ref.T {
			if _, ok := loc.T[key]; !ok {
				return nil, fmt.Errorf("locale %s: missing t.%s", loc.Code, key)
			}
		}
		for key := range ref.H {
			if _, ok := loc.H[key]; !ok {
				return nil, fmt.Errorf("locale %s: missing h.%s", loc.Code, key)
			}
		}
	}
	sort.SliceStable(locales, func(i, j int) bool {
		if locales[i].Code == "en" {
			return true
		}
		if locales[j].Code == "en" {
			return false
		}
		return locales[i].Code < locales[j].Code
	})
	return locales, nil
}

// sourceDate is the date used as lastmod / dateModified. It is stable across
// regenerations: the last commit that touched the sources, or today when the
// sources have uncommitted changes (or git is unavailable).
func sourceDate() string {
	sources := []string{"public/engines.json", "templates", "locales", "cmd"}
	today := time.Now().Format("2006-01-02")

	status, err := exec.Command("git", append([]string{"status", "--porcelain", "--"}, sources...)...).Output()
	if err != nil || len(bytes.TrimSpace(status)) > 0 {
		return today
	}
	out, err := exec.Command("git", append([]string{"log", "-1", "--format=%cs", "--"}, sources...)...).Output()
	if err != nil || len(bytes.TrimSpace(out)) == 0 {
		return today
	}
	return string(bytes.TrimSpace(out))
}

func fill(s string, vars map[string]string) string {
	for k, v := range vars {
		s = strings.ReplaceAll(s, "{"+k+"}", v)
	}
	return s
}

func fillAll(m map[string]string, vars map[string]string) map[string]string {
	out := make(map[string]string, len(m))
	for k, v := range m {
		out[k] = fill(v, vars)
	}
	return out
}

// fillAllHTML is fillAll for strings that carry markup: the values are escaped,
// so a "&" in an assistant's URL or a "<" in a name cannot corrupt the HTML.
func fillAllHTML(m map[string]string, vars map[string]string) map[string]string {
	escaped := make(map[string]string, len(vars))
	for k, v := range vars {
		escaped[k] = html.EscapeString(v)
	}
	return fillAll(m, escaped)
}

func toHTML(m map[string]string) map[string]template.HTML {
	out := make(map[string]template.HTML, len(m))
	for k, v := range m {
		out[k] = template.HTML(v)
	}
	return out
}

func (loc *Locale) prefillLabel(e Engine) string {
	switch e.Prefill {
	case "yes":
		return loc.T["prefill_yes"]
	case "partial":
		return loc.T["prefill_partial"]
	default:
		return loc.T["prefill_none"]
	}
}

// localized returns the engine with notes / account replaced by the locale's text when present.
func (loc *Locale) localized(e Engine) Engine {
	if t, ok := loc.Engines[e.Slug]; ok {
		if t.Notes != "" {
			e.Notes = t.Notes
		}
		if t.Account != "" {
			e.Account = t.Account
		}
	}
	return e
}

func (loc *Locale) aiRows(ai []Engine, skip string) []aiRow {
	var rows []aiRow
	for _, e := range ai {
		if e.Slug == skip {
			continue
		}
		e = loc.localized(e)
		rows = append(rows, aiRow{
			Slug: e.Slug, Name: e.Name, Label: loc.prefillLabel(e), Notes: e.Notes,
			Href: loc.Path + "/" + e.Slug + "/", Icon: e.Icon, Mono: e.Mono,
			LinkText: fill(loc.T["e_other_link"], map[string]string{"name": e.Name, "short": e.Short()}),
		})
	}
	return rows
}

// alternates lists every locale's version of a page (relative path after the locale prefix).
func alternates(site Site, locales []*Locale, current *Locale, rel string) ([]Alternate, string) {
	var alts []Alternate
	var xdefault string
	for _, loc := range locales {
		href := site.URL + loc.Path + rel
		alts = append(alts, Alternate{Code: loc.Code, Name: loc.Name, Href: href, RelHref: loc.Path + rel, Current: loc == current})
		if loc.Code == "en" {
			xdefault = href
		}
	}
	return alts, xdefault
}

func jsonJS(v interface{}, indent string) (template.JS, error) {
	var b []byte
	var err error
	if indent == "" {
		b, err = json.Marshal(v)
	} else {
		b, err = json.MarshalIndent(v, indent, "    ")
	}
	if err != nil {
		return "", err
	}
	// json.Marshal escapes <, > and & so "</script>" cannot appear inside a script block
	return template.JS(b), nil
}

// writePage renders one page and returns its slash-separated path.
func writePage(tmpl *template.Template, name, path string, data interface{}) (string, error) {
	var out bytes.Buffer
	if err := tmpl.ExecuteTemplate(&out, name, data); err != nil {
		return "", fmt.Errorf("%s: %w", path, err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	return filepath.ToSlash(path), os.WriteFile(path, out.Bytes(), 0o644)
}

func renderIndex(tmpl *template.Template, data Data, ai []Engine, locales []*Locale, loc *Locale, today string) (string, error) {
	vars := map[string]string{"site": data.Site.URL, "path": loc.Path}
	t := fillAll(loc.T, vars)
	h := fillAllHTML(loc.H, vars)
	alts, xdefault := alternates(data.Site, locales, loc, "/")
	canonical := data.Site.URL + loc.Path + "/"

	ogImage := data.Site.URL + "/og-image.png"
	if loc.Code != "en" {
		ogImage = data.Site.URL + "/og/" + loc.Code + "/home.png"
	}

	var faq []FAQ
	for _, f := range loc.FAQ {
		faq = append(faq, FAQ{Q: fill(f.Q, vars), A: fill(f.A, vars)})
	}
	var faqEntities []map[string]interface{}
	for _, f := range faq {
		faqEntities = append(faqEntities, map[string]interface{}{
			"@type": "Question", "name": f.Q,
			"acceptedAnswer": map[string]string{"@type": "Answer", "text": f.A},
		})
	}
	jsonld, err := jsonJS(map[string]interface{}{
		"@context": "https://schema.org",
		"@graph": []interface{}{
			map[string]interface{}{
				"@type": "WebSite", "@id": canonical + "#website", "url": canonical, "name": data.Site.Name,
				"alternateName": []string{"Search GPT For Me", t["alternate_name"]},
				"description":   t["description"], "inLanguage": loc.HTMLLang,
				"potentialAction": map[string]interface{}{
					"@type":       "SearchAction",
					"target":      map[string]string{"@type": "EntryPoint", "urlTemplate": canonical + "?q={search_term_string}"},
					"query-input": "required name=search_term_string",
				},
			},
			map[string]interface{}{
				"@type": "WebApplication", "@id": canonical + "#app", "name": data.Site.Name, "url": canonical,
				"description": t["description"], "applicationCategory": "UtilitiesApplication", "operatingSystem": "Any",
				"browserRequirements": "Requires JavaScript", "isAccessibleForFree": true, "inLanguage": loc.HTMLLang,
				"offers":       map[string]string{"@type": "Offer", "price": "0", "priceCurrency": "USD"},
				"image":        ogImage,
				"author":       map[string]string{"@type": "Person", "name": "Yaroslav Podorvanov", "url": "https://github.com/YaroslavPodorvanov"},
				"license":      "https://github.com/readytotouch/chatgptforme/blob/main/LICENSE",
				"sameAs":       []string{"https://github.com/readytotouch/chatgptforme"},
				"dateModified": today,
			},
			map[string]interface{}{"@type": "FAQPage", "@id": canonical + "#faq", "mainEntity": faqEntities},
		},
	}, "    ")
	if err != nil {
		return "", err
	}
	groups, err := jsonJS(data.Groups, "    ")
	if err != nil {
		return "", err
	}
	i18n, err := jsonJS(pick(t, "ask_all_opens", "select_one", "blocked", "search", "copy", "open", "copy_prompt",
		"copy_only_title", "via_google", "copied", "copy_failed"), "    ")
	if err != nil {
		return "", err
	}

	page := indexPage{
		basePage: basePage{
			Site: data.Site, L: loc, T: t, H: toHTML(h), Canonical: canonical, OGImage: ogImage,
			Alternates: alts, XDefault: xdefault, HomeHref: loc.Path + "/",
			BookmarkletTarget: canonical + "?q=", JSONLD: jsonld, I18nJSON: i18n, Today: today,
		},
		FAQ: faq, AI: loc.aiRows(ai, ""), GroupsJSON: groups,
	}
	return writePage(tmpl, "index.html", filepath.Join("public", loc.Path, "index.html"), page)
}

func renderEngine(tmpl *template.Template, data Data, ai []Engine, locales []*Locale, loc *Locale, e Engine, today string) (string, error) {
	e = loc.localized(e)
	vars := map[string]string{
		"site": data.Site.URL, "path": loc.Path, "name": e.Name, "short": e.Short(),
		"vendor": e.Vendor, "slug": e.Slug, "url": e.URL,
	}
	t := fillAll(loc.T, vars)
	h := fillAllHTML(loc.H, vars)
	rel := "/" + e.Slug + "/"
	alts, xdefault := alternates(data.Site, locales, loc, rel)
	canonical := data.Site.URL + loc.Path + rel

	ogImage := data.Site.URL + "/og/" + e.Slug + ".png"
	if loc.Code != "en" {
		ogImage = data.Site.URL + "/og/" + loc.Code + "/" + e.Slug + ".png"
	}

	jsonld, err := jsonJS(map[string]interface{}{
		"@context": "https://schema.org",
		"@graph": []interface{}{
			map[string]interface{}{
				"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical,
				"name": t["e_h1"], "description": t["e_og_description"],
				"isPartOf":     map[string]string{"@id": data.Site.URL + loc.Path + "/#website"},
				"dateModified": today, "inLanguage": loc.HTMLLang,
			},
			map[string]interface{}{
				"@type": "BreadcrumbList",
				"itemListElement": []map[string]interface{}{
					{"@type": "ListItem", "position": 1, "name": data.Site.Name, "item": data.Site.URL + loc.Path + "/"},
					{"@type": "ListItem", "position": 2, "name": e.Name, "item": canonical},
				},
			},
		},
	}, "    ")
	if err != nil {
		return "", err
	}
	engineJSON, err := jsonJS(e, "")
	if err != nil {
		return "", err
	}
	i18n, err := jsonJS(pick(t, "e_enter_prompt_first", "e_link_copied", "e_prompt_copied", "copy_failed"), "    ")
	if err != nil {
		return "", err
	}

	page := enginePage{
		basePage: basePage{
			Site: data.Site, L: loc, T: t, H: toHTML(h), Canonical: canonical, OGImage: ogImage,
			Alternates: alts, XDefault: xdefault, HomeHref: loc.Path + "/",
			BookmarkletTarget: canonical + "?go=1&q=", JSONLD: jsonld, I18nJSON: i18n, Today: today,
		},
		Engine: e, Others: loc.aiRows(ai, e.Slug), EngineJSON: engineJSON,
	}
	return writePage(tmpl, "engine.html", filepath.Join("public", loc.Path, e.Slug, "index.html"), page)
}

func pick(m map[string]string, keys ...string) map[string]string {
	out := make(map[string]string, len(keys))
	for _, k := range keys {
		out[k] = m[k]
	}
	return out
}

// writeSitemaps writes the sitemap index and the main sitemap with the same lastmod.
func writeSitemaps(site Site, ai []Engine, locales []*Locale, today string) error {
	index := "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n" +
		"    <sitemap>\n        <loc>" + site.URL + "/sitemap-main.xml</loc>\n        <lastmod>" + today + "</lastmod>\n    </sitemap>\n</sitemapindex>\n"
	if err := os.WriteFile("public/sitemap.xml", []byte(index), 0o644); err != nil {
		return err
	}

	var b bytes.Buffer
	b.WriteString("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
	b.WriteString("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\" xmlns:xhtml=\"http://www.w3.org/1999/xhtml\">\n")
	url := func(rel, freq, prio string) {
		for _, loc := range locales {
			fmt.Fprintf(&b, "    <url>\n        <loc>%s%s%s</loc>\n        <lastmod>%s</lastmod>\n        <changefreq>%s</changefreq>\n        <priority>%s</priority>\n",
				site.URL, loc.Path, rel, today, freq, prio)
			for _, alt := range locales {
				fmt.Fprintf(&b, "        <xhtml:link rel=\"alternate\" hreflang=\"%s\" href=\"%s%s%s\"/>\n", alt.Code, site.URL, alt.Path, rel)
			}
			fmt.Fprintf(&b, "        <xhtml:link rel=\"alternate\" hreflang=\"x-default\" href=\"%s%s\"/>\n    </url>\n", site.URL, rel)
		}
	}
	url("/", "weekly", "1.0")
	for _, e := range ai {
		url("/"+e.Slug+"/", "monthly", "0.8")
	}
	b.WriteString("</urlset>\n")
	return os.WriteFile("public/sitemap-main.xml", b.Bytes(), 0o644)
}
