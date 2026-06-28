#!/usr/bin/env python3
import os
import re
import markdown
from playwright.sync_api import sync_playwright

def convert_markdown_to_pdf():
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    readme_path = os.path.join(current_dir, "README_zh.md")
    pdf_path = os.path.join(current_dir, "README_zh.pdf")
    
    print(f"Reading Markdown from: {readme_path}")
    with open(readme_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Replace relative image paths like 'assets/images/...' with absolute file URIs
    # so that Chromium can resolve them locally.
    def replace_img_path(match):
        img_src = match.group(1)
        if not img_src.startswith(("http://", "https://", "data:", "file://")):
            # Convert to absolute path
            abs_img_path = os.path.join(current_dir, img_src)
            # Create file:// URI
            return f'src="file://{abs_img_path}"'
        return match.group(0)

    # Replace both <img src="..." and Markdown image syntax ![]()
    # Let's first replace HTML <img> tags
    html_img_pattern = re.compile(r'src=["\']([^"\']+)["\']')
    md_content = html_img_pattern.sub(replace_img_path, md_content)
    
    # Convert Markdown to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=["fenced_code", "tables"]
    )

    # Build the full beautiful HTML document
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
  
  body {{
    font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #1f2328;
    background-color: #ffffff;
    line-height: 1.6;
    font-size: 14px;
    padding: 0;
    margin: 0;
  }}
  
  h1, h2, h3, h4, h5, h6 {{
    color: #0969da;
    font-weight: 600;
    margin-top: 24px;
    margin-bottom: 16px;
    line-height: 1.25;
  }}
  
  h1 {{
    font-size: 2.25em;
    padding-bottom: 0.3em;
    border-bottom: 1px solid #d0d7de;
    color: #1f2328;
    text-align: center;
  }}
  
  h2 {{
    font-size: 1.5em;
    padding-bottom: 0.3em;
    border-bottom: 1px solid #d0d7de;
    margin-top: 36px;
  }}
  
  h3 {{
    font-size: 1.25em;
  }}
  
  p, ul, ol, dl, table, blockquote {{
    margin-top: 0;
    margin-bottom: 16px;
  }}
  
  a {{
    color: #0969da;
    text-decoration: none;
  }}
  
  a:hover {{
    text-decoration: underline;
  }}
  
  blockquote {{
    padding: 0 1em;
    color: #656d76;
    border-left: 0.25em solid #d0d7de;
    margin: 16px 0;
    font-style: italic;
    background-color: #f6f8fa;
    border-radius: 4px;
    padding-top: 8px;
    padding-bottom: 8px;
  }}
  
  code {{
    font-family: 'JetBrains Mono', SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 85%;
    background-color: rgba(175, 184, 193, 0.2);
    padding: 0.2em 0.4em;
    border-radius: 6px;
  }}
  
  pre {{
    background-color: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 8px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
  }}
  
  pre code {{
    background-color: transparent;
    padding: 0;
    font-size: 100%;
    color: inherit;
    border-radius: 0;
  }}
  
  table {{
    border-spacing: 0;
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 16px;
  }}
  
  table th {{
    font-weight: 600;
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    padding: 8px 12px;
  }}
  
  table td {{
    border: 1px solid #d0d7de;
    padding: 8px 12px;
  }}
  
  table tr:nth-child(even) {{
    background-color: #f6f8fa;
  }}
  
  img {{
    max-width: 100%;
    box-sizing: content-box;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    margin: 20px auto;
    display: block;
  }}
  
  hr {{
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #d0d7de;
    border: 0;
  }}
  
  /* Avoid orphan headers and keep sections clean */
  h1, h2, h3, h4, h5, h6 {{
    page-break-after: avoid;
  }}
  
  pre, blockquote, table, img {{
    page-break-inside: avoid;
  }}
  
  .center-align {{
    text-align: center;
  }}
  
</style>
</head>
<body>
<div style="padding: 10px;">
  {html_body}
</div>
</body>
</html>
"""

    temp_html_path = os.path.join(current_dir, "temp_readme.html")
    print(f"Writing parsed HTML to: {temp_html_path}")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Launching Playwright for PDF export...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Load local HTML file
        page.goto(f"file://{temp_html_path}")
        
        # Wait a small delay to make sure styles and fonts are applied
        page.wait_for_timeout(1000)
        
        print("Rendering PDF...")
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "20mm",
                "right": "20mm"
            },
            display_header_footer=True,
            header_template='<span style="font-size: 9px; color: #888; width: 100%; text-align: center; font-family: sans-serif;">Trade Nothing - 中文说明文档</span>',
            footer_template='<div style="font-size: 9px; color: #888; width: 100%; text-align: center; font-family: sans-serif;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>'
        )
        browser.close()

    # Clean up the temporary HTML file
    if os.path.exists(temp_html_path):
        os.remove(temp_html_path)
        
    print(f"🎉 PDF successfully generated at: {pdf_path}")

if __name__ == "__main__":
    convert_markdown_to_pdf()
