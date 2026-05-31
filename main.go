package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	userAgent  = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
	listenAddr = ":8899"
)

var httpClient = &http.Client{Timeout: 30 * time.Second}

type APIResp struct {
	Status string          `json:"status"`
	Data   json.RawMessage `json:"data"`
}
type AccountData struct {
	Token string `json:"token"`
}
type ContentsData struct {
	Children map[string]FileChild `json:"children"`
}
type FileChild struct {
	ID             string `json:"id"`
	Type           string `json:"type"`
	Name           string `json:"name"`
	Size           int64  `json:"size"`
	ServerSelected string `json:"serverSelected"`
	Link           string `json:"link"`
	MimeType       string `json:"mimetype"`
}

type Result struct {
	Status string       `json:"status"`
	Code   string       `json:"code"`
	Files  []FileResult `json:"files"`
	Error  string       `json:"error,omitempty"`
}
type FileResult struct {
	Name     string `json:"name"`
	Size     int64  `json:"size"`
	SizeH    string `json:"size_human"`
	URL      string `json:"url"`
	Cookie   string `json:"cookie"`
	MimeType string `json:"mimetype,omitempty"`
}

func doReq(method, rawURL, token string, extra map[string]string) (*http.Response, error) {
	req, _ := http.NewRequest(method, rawURL, nil)
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "*/*")
	req.Header.Set("Origin", "https://gofile.io")
	req.Header.Set("Referer", "https://gofile.io/")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	for k, v := range extra {
		req.Header.Set(k, v)
	}
	return httpClient.Do(req)
}

func apiCall(method, rawURL, token string, extra map[string]string) (*APIResp, error) {
	resp, err := doReq(method, rawURL, token, extra)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var r APIResp
	json.NewDecoder(resp.Body).Decode(&r)
	return &r, nil
}

// hexEscape matches JS \xNN escapes; gofile hex-escapes the literals in
// wt.obf.js so we must decode them before the salt regex can match.
var hexEscape = regexp.MustCompile(`\\x([0-9a-fA-F]{2})`)

func decodeHexEscapes(s string) string {
	return hexEscape.ReplaceAllStringFunc(s, func(m string) string {
		n, _ := strconv.ParseInt(m[2:], 16, 32)
		return string(rune(n))
	})
}

func hasDigitAndAlpha(s string) bool {
	var d, a bool
	for _, c := range s {
		if c >= '0' && c <= '9' {
			d = true
		} else if c >= 'a' && c <= 'z' {
			a = true
		}
	}
	return d && a
}

func fetchWTSalt() string {
	const fallback = "g4f8fd9f12h14g"
	resp, err := doReq("GET", "https://gofile.io/dist/js/wt.obf.js", "", nil)
	if err != nil {
		return fallback
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	js := decodeHexEscapes(string(body))
	idx := strings.Index(js, "generateWT")
	if idx == -1 {
		return fallback
	}
	end := idx + 4000
	if end > len(js) {
		end = len(js)
	}
	re := regexp.MustCompile(`['"]([a-z0-9]{10,20})['"]`)
	for _, m := range re.FindAllStringSubmatch(js[idx:end], -1) {
		if hasDigitAndAlpha(m[1]) {
			return m[1]
		}
	}
	return fallback
}

func generateWT(token, salt string) string {
	ts := strconv.FormatInt(time.Now().Unix()/14400, 10)
	input := fmt.Sprintf("%s::en-US::%s::%s::%s", userAgent, token, ts, salt)
	h := sha256.Sum256([]byte(input))
	return fmt.Sprintf("%x", h)
}

func resolveGofile(code string) Result {
	salt := fetchWTSalt()

	// Create account
	r, err := apiCall("POST", "https://api.gofile.io/accounts", "", nil)
	if err != nil || r.Status != "ok" {
		return Result{Status: "error", Code: code, Error: fmt.Sprintf("account: %v", err)}
	}
	var acc AccountData
	json.Unmarshal(r.Data, &acc)

	wt := generateWT(acc.Token, salt)

	// Register session
	apiCall("GET", "https://api.gofile.io/accounts/website", acc.Token, nil)

	// Get contents
	u := fmt.Sprintf("https://api.gofile.io/contents/%s?contentFilter=&page=1&pageSize=1000&sortField=name&sortDirection=1", code)
	r2, err := apiCall("GET", u, acc.Token, map[string]string{
		"X-Website-Token": wt,
		"X-BL":            "en-US",
	})
	if err != nil || r2.Status != "ok" {
		errMsg := "unknown"
		if err != nil {
			errMsg = err.Error()
		} else {
			errMsg = r2.Status
		}
		return Result{Status: "error", Code: code, Error: errMsg}
	}

	var contents ContentsData
	json.Unmarshal(r2.Data, &contents)

	var files []FileResult
	for _, f := range contents.Children {
		if f.Type != "file" {
			continue
		}
		dlURL := f.Link
		if dlURL == "" {
			dlURL = fmt.Sprintf("https://%s.gofile.io/download/web/%s/%s",
				f.ServerSelected, f.ID, url.PathEscape(f.Name))
		}
		files = append(files, FileResult{
			Name:     f.Name,
			Size:     f.Size,
			SizeH:    humanSize(f.Size),
			URL:      dlURL,
			Cookie:   "accountToken=" + acc.Token,
			MimeType: f.MimeType,
		})
	}

	return Result{Status: "ok", Code: code, Files: files}
}

func extractCode(input string) string {
	if i := strings.Index(input, "/d/"); i >= 0 {
		return strings.TrimRight(input[i+3:], "/ ")
	}
	return strings.TrimSpace(input)
}

func handler(w http.ResponseWriter, r *http.Request) {
	link := r.URL.Query().Get("url")
	if link == "" {
		link = r.URL.Query().Get("code")
	}
	if link == "" {
		// Try path: /dP2rRR
		path := strings.TrimPrefix(r.URL.Path, "/")
		if path != "" && path != "favicon.ico" {
			link = path
		}
	}
	if link == "" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"usage": "GET /?url=https://gofile.io/d/CODE or GET /CODE",
		})
		return
	}

	code := extractCode(link)
	result := resolveGofile(code)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func humanSize(b int64) string {
	if b < 1024 {
		return fmt.Sprintf("%d B", b)
	}
	fb := float64(b)
	for _, u := range []string{"KB", "MB", "GB", "TB"} {
		fb /= 1024
		if fb < 1024 {
			return fmt.Sprintf("%.1f %s", fb, u)
		}
	}
	return fmt.Sprintf("%.1f PB", fb/1024)
}

func main() {
	fmt.Printf("Gofile resolver listening on %s\n", listenAddr)
	fmt.Println("  GET /?url=https://gofile.io/d/CODE")
	fmt.Println("  GET /CODE")
	http.HandleFunc("/", handler)
	http.ListenAndServe(listenAddr, nil)
}
