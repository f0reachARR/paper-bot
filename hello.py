from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
import os
from magic_pdf.pipe.UNIPipe import UNIPipe
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

image_writer = DiskReaderWriter("./images")
image_dir = str(os.path.basename("./images"))

jso_useful_key = {"_pdf_type": "", "model_list": []}
pdf_bytes = open("./ICST24_Course_Mapping.pdf", "rb").read()
pipe: UNIPipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)
pipe.pipe_classify()
pipe.pipe_analyze()
pipe.pipe_parse()
md_content: str = pipe.pipe_mk_markdown(image_dir, drop_mode="none")

output = open("raw.md", "w")
output.write(md_content)
output.close()

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

output = open("output2.md", "w")

for section in range(1, 7):
    prompt = f"この論文の{section}章のみを日本語に翻訳してください。出力はMarkdownで、$で囲まれた数式や、Markdownのリンクはそのまま保持してください。"
    content = model.generate_content(
        [
            md_content,
            prompt,
        ],
    )

    output.write(content.text)
    output.write("-------------------------------------------\n\n")

    print(content.text)


output.close()
