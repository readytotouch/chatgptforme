// Command generate builds everything that derives from public/engines.json:
//   - the engine list embedded in public/index.html (between marker comments)
//   - the "Supported AI assistants" table rows in public/index.html
//   - one landing page per AI assistant: public/<slug>/index.html
//   - public/sitemap-main.xml
//
// Run it from the repository root: go run ./cmd/generate
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"os"
	"path/filepath"
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
	URL              string `json:"url"`
	Signature        string `json:"signature,omitempty"`
	Prefill          string `json:"prefill,omitempty"` // yes | partial | none (AI assistants only)
	Notes            string `json:"notes,omitempty"`
	Account          string `json:"account,omitempty"`
	GoogleSitePrefix string `json:"googleSitePrefix,omitempty"`
}

type Group struct {
	GroupName string   `json:"groupName"`
	Engines   []Engine `json:"engines"`
}

type Data struct {
	Site   Site    `json:"site"`
	Groups []Group `json:"groups"`
}

func (e Engine) Short() string {
	if e.ShortName != "" {
		return e.ShortName
	}
	return e.Name
}

func (e Engine) PrefillLabel() string {
	switch e.Prefill {
	case "yes":
		return "Yes"
	case "partial":
		return "Partial"
	default:
		return "Copy only"
	}
}

func (e Engine) CopyOnly() bool { return e.Prefill == "none" }

type pageData struct {
	Site       Site
	Engine     Engine
	Others     []Engine
	EngineJSON template.JS
	Today      string
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "generate:", err)
		os.Exit(1)
	}
}

func run() error {
	raw, err := os.ReadFile("public/engines.json")
	if err != nil {
		return err
	}
	var data Data
	if err := json.Unmarshal(raw, &data); err != nil {
		return fmt.Errorf("engines.json: %w", err)
	}

	var ai []Engine
	for _, g := range data.Groups {
		if g.GroupName == "AI Assistants" {
			ai = g.Engines
		}
	}
	if len(ai) == 0 {
		return fmt.Errorf("engines.json: no \"AI Assistants\" group")
	}
	for _, e := range ai {
		if e.Slug == "" || e.Prefill == "" {
			return fmt.Errorf("engines.json: AI assistant %q needs slug and prefill", e.Name)
		}
	}

	today := time.Now().Format("2006-01-02")

	if err := updateIndex(data, ai); err != nil {
		return err
	}
	if err := renderEnginePages(data, ai, today); err != nil {
		return err
	}
	return writeSitemap(data.Site, ai, today)
}

// replaceBetween swaps the content between two marker lines, keeping the markers.
func replaceBetween(src, start, end, body string) (string, error) {
	i := strings.Index(src, start)
	j := strings.Index(src, end)
	if i < 0 || j < 0 || j < i {
		return "", fmt.Errorf("markers %q / %q not found", start, end)
	}
	i += len(start)
	return src[:i] + "\n" + body + "\n" + src[j:], nil
}

func updateIndex(data Data, ai []Engine) error {
	const path = "public/index.html"
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	src := string(b)

	groups, err := json.MarshalIndent(data.Groups, "    ", "    ")
	if err != nil {
		return err
	}
	src, err = replaceBetween(src, "    // engines:start", "    // engines:end",
		"    const searchGroups = "+string(groups)+";")
	if err != nil {
		return err
	}

	var rows bytes.Buffer
	for i, e := range ai {
		border := ` class="border-b border-gray-100"`
		if i == len(ai)-1 {
			border = ""
		}
		fmt.Fprintf(&rows,
			"                    <tr%s><td class=\"py-2 pr-3\"><a href=\"/%s/\" class=\"text-blue-500 hover:underline\">%s</a></td><td class=\"py-2 pr-3\">%s</td><td class=\"py-2\">%s</td></tr>\n",
			border, e.Slug, template.HTMLEscapeString(e.Name), e.PrefillLabel(), template.HTMLEscapeString(e.Notes))
	}
	src, err = replaceBetween(src, "                    <!-- ai-table:start -->", "                    <!-- ai-table:end -->",
		strings.TrimRight(rows.String(), "\n"))
	if err != nil {
		return err
	}
	return os.WriteFile(path, []byte(src), 0o644)
}

func renderEnginePages(data Data, ai []Engine, today string) error {
	tmpl, err := template.ParseFiles("templates/engine.html")
	if err != nil {
		return err
	}
	for _, e := range ai {
		var others []Engine
		for _, o := range ai {
			if o.Slug != e.Slug {
				others = append(others, o)
			}
		}
		ej, err := json.Marshal(e) // json.Marshal escapes <, > and & so "</script>" cannot appear
		if err != nil {
			return err
		}
		var out bytes.Buffer
		if err := tmpl.Execute(&out, pageData{
			Site: data.Site, Engine: e, Others: others, EngineJSON: template.JS(ej), Today: today,
		}); err != nil {
			return fmt.Errorf("%s: %w", e.Slug, err)
		}
		dir := filepath.Join("public", e.Slug)
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "index.html"), out.Bytes(), 0o644); err != nil {
			return err
		}
	}
	return nil
}

func writeSitemap(site Site, ai []Engine, today string) error {
	var b bytes.Buffer
	b.WriteString("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
	b.WriteString("<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n")
	url := func(loc, freq, prio string) {
		fmt.Fprintf(&b, "    <url>\n        <loc>%s</loc>\n        <lastmod>%s</lastmod>\n        <changefreq>%s</changefreq>\n        <priority>%s</priority>\n    </url>\n", loc, today, freq, prio)
	}
	url(site.URL+"/", "weekly", "1.0")
	for _, e := range ai {
		url(site.URL+"/"+e.Slug+"/", "monthly", "0.8")
	}
	b.WriteString("</urlset>\n")
	return os.WriteFile("public/sitemap-main.xml", b.Bytes(), 0o644)
}
