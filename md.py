import os
import re
from markdown import Extension
from markdown.inlinepatterns import LinkInlineProcessor
import xml.etree.ElementTree as etree
import base64


class ImageInlineProcessor(LinkInlineProcessor):
    """Return a `img` element from the given match."""

    def handleMatch(
        self, m: re.Match[str], data: str
    ) -> tuple[etree.Element | None, int | None, int | None]:
        """Return an `img` [`Element`][xml.etree.ElementTree.Element] or `(None, None, None)`."""
        text, index, handled = self.getText(data, m.end(0))
        if not handled:
            return None, None, None

        src, title, index, handled = self.getLink(data, index)
        if not handled:
            return None, None, None

        el = etree.Element("img")

        if src.startswith("images/") and os.path.exists(src):
            with open(src, "rb") as f:
                base64_src = base64.b64encode(f.read()).decode("utf-8")
                el.set("src", "data:image/png;base64," + base64_src)
        else:
            el.set("src", src)

        if title is not None:
            el.set("title", title)

        el.set("alt", self.unescape(text))
        return el, m.start(0), index


IMAGE_LINK_RE = r"\!\["


class PdfExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.deregister("image_link")
        md.inlinePatterns.register(
            ImageInlineProcessor(IMAGE_LINK_RE, md), "image_link", 150
        )


MATHJAX = """
<script type="text/javascript" src="https://cdn.jsdelivr.net/npm/mathjax@2/MathJax.js">
</script>
<script type="text/x-mathjax-config">
MathJax.Hub.Config({
  config: ["MMLorHTML.js"],
  jax: ["input/TeX", "output/HTML-CSS", "output/NativeMML"],
  extensions: ["MathMenu.js", "MathZoom.js"]
});
</script>
"""


def convert_markdown(md_content: str) -> str:
    from markdown import markdown

    return MATHJAX + markdown(
        md_content,
        extensions=[PdfExtension(), "mdx_math"],
        extension_configs={"mdx_math": {"enable_dollar_delimiter": True}},
    )
