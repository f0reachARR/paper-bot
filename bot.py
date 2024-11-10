from io import BytesIO
import os
import time
from typing import Optional
from dotenv import load_dotenv
import discord
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
from magic_pdf.pipe.UNIPipe import UNIPipe
import google.generativeai as genai

from md import convert_markdown

load_dotenv()

TRANSLATION_MODEL = "gemini-1.5-flash"

TRANSLATION_SYSTEM_PROMPT = (
    "あなたは翻訳を職業としています。正確で抜けがなく、誤りのない翻訳が必要とされています。"
    + "また、語尾を均一にするなど、文章スタイルを均一にすることも重要な仕事です。"
    + "与えられる文章はMarkdown形式で、$で囲まれる数式が含まれます。数式については変更する必要はありません。"
)

TRANSLATION_PROMPT = "この論文を日本語に翻訳してください。翻訳が完了したら「This is end of translation.」と出力してください。参考文献は省略してください。"

TRANSLATION_CONFIG = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
    "stop_sequences": [
        "This is end of translation.",
    ],
}

SUMMARY_MODEL = "gemini-1.5-pro"

SUMMARY_SYSTEM_PROMPT = (
    "あなたは大学の教授で、研究室の学生に論文を解説しています。"
    + "論文を解説する上で重要なのは、先行研究、仮説、実験、結論のような流れを意識した解説です。"
    + "具体的な数値や手法を示すことでより理解される解説になります。"
    + "スライド資料の場合、実験に対応するRQなど、関係性を示すとわかりやすくなります。"
)

SUMMARY_JA_PROMPT = "この論文を日本語でまとめて、解説してください。具体的な数値を含め、プレゼン資料20ページ程度の分量で解説したいです。"

SUMMARY_EN_SLIDE_PROMPT = (
    "この論文を英語でまとめて、20ページ程度の解説用のスライド資料をMarkdownで作成してください。"
    + "箇条書きを用いるなど、スライド資料としてそのまま利用できる形式にしてください。"
)

SUMMARY_CONFIG = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)


class PaperBot(discord.Client):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

    def make_markdown(self, pdf_bytes: bytes):
        image_writer = DiskReaderWriter("./images")
        image_dir = str(os.path.basename("./images"))

        jso_useful_key = {"_pdf_type": "", "model_list": []}
        pipe: UNIPipe = UNIPipe(pdf_bytes, jso_useful_key, image_writer)
        pipe.pipe_classify()
        pipe.pipe_analyze()
        pipe.pipe_parse()
        md_content: str = pipe.pipe_mk_markdown(image_dir, drop_mode="none")

        return md_content

    def upload_markdown(self, md_content: str):
        # Markdownをファイルとしてupload
        gemini_file = genai.upload_file(
            BytesIO(md_content.encode("utf-8")), mime_type="text/markdown"
        )

        print(f"Uploaded file: {gemini_file.name}")

        # ACTIVEになるまで待機
        while True:
            gemini_file = genai.get_file(gemini_file.name)
            if gemini_file.state.name == "ACTIVE":
                break

            time.sleep(1)

        return gemini_file

    def translate_markdown(self, md_content: str):
        model = genai.GenerativeModel(
            model_name=TRANSLATION_MODEL,
            generation_config=TRANSLATION_CONFIG,
            system_instruction=TRANSLATION_SYSTEM_PROMPT,
        )

        # Markdownをファイルとしてupload
        gemini_file = self.upload_markdown(md_content)

        print("Starting chat session")

        chat_session = model.start_chat()

        debug_file = open("debug.txt", "w+")

        response = chat_session.send_message(
            content={
                "role": "user",
                "parts": [
                    gemini_file,
                    TRANSLATION_PROMPT,
                ],
            },
        )

        translated_md = response.text

        debug_file.write(translated_md)

        print(f"First response length: {len(translated_md)}")

        while True:
            time.sleep(30)
            response = chat_session.send_message(
                content={
                    "role": "user",
                    "parts": [
                        "続きを出力してください。",
                    ],
                },
            )

            translated_md += response.text

            debug_file.write(response.text)

            print(f"Response length: {len(response.text)}/{len(translated_md)}")

            if "This is end of translation." in response.text:
                break

            if len(response.text) < 500:
                break

        debug_file.close()

        return translated_md

    def summarize_markdown(self, md_content: str, type: str):
        model = genai.GenerativeModel(
            model_name=SUMMARY_MODEL,
            generation_config=SUMMARY_CONFIG,
            system_instruction=SUMMARY_SYSTEM_PROMPT,
        )
        gemini_file = self.upload_markdown(md_content)

        if type == "ja_summary":
            prompt = SUMMARY_JA_PROMPT
        elif type == "en_slide":
            prompt = SUMMARY_EN_SLIDE_PROMPT
        else:
            raise ValueError("Invalid type")

        response = model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [
                        gemini_file,
                        prompt,
                    ],
                }
            ]
        )

        return response.text

    async def on_message(self, message: discord.Message):
        print(f"Message from {message.author}: {message.content}")

        if message.author == self.user:
            return

        # DMのみ
        if not isinstance(message.channel, discord.DMChannel):
            return

        attachment: Optional[discord.Attachment] = None

        # リプライの場合、リプライ先を取得
        if message.reference is not None and message.reference:
            print(f"Reference message: {message.reference.message_id}")
            reference_message = await message.channel.fetch_message(
                message.reference.message_id
            )
            if len(reference_message.attachments) > 0:
                attachment = reference_message.attachments[0]

        if attachment is None:
            attachment = (
                message.attachments[0] if len(message.attachments) > 0 else None
            )

        if attachment is None:
            return

        # PDFファイルが添付されているか確認
        if attachment.filename.endswith(".pdf") and message.content == "translate":
            pdf_bytes = await attachment.read()
            print(f"Received PDF file: {attachment.filename}")

            await message.channel.send(
                "PDFファイルを受け付けました。解析を開始します。"
            )

            md_content = await client.loop.run_in_executor(
                None, self.make_markdown, pdf_bytes
            )

            await message.channel.send(
                "PDFファイルの解析が完了しました。英文Markdownを送信します。続いてGeminiによる日本語翻訳を行います。",
                file=discord.File(
                    fp=BytesIO(md_content.encode("utf-8")), filename="english.md"
                ),
            )

            translated_md = await client.loop.run_in_executor(
                None, self.translate_markdown, md_content
            )

            await message.channel.send(
                "日本語翻訳が完了しました。日本語Markdownを送信します。",
                file=discord.File(
                    fp=BytesIO(translated_md.encode("utf-8")), filename="japanese.md"
                ),
            )

        # Markdownファイルが「translate」のメッセージとともに添付されているか確認
        elif attachment.filename.endswith(".md") and message.content == "translate":
            md_bytes = await attachment.read()
            print(f"Received Markdown file: {attachment.filename}")

            await message.channel.send(
                "Markdownファイルを受け付けました。翻訳を開始します。"
            )

            md_content = md_bytes.decode("utf-8")

            translated_md = await client.loop.run_in_executor(
                None, self.translate_markdown, md_content
            )

            await message.channel.send(
                "日本語翻訳が完了しました。日本語Markdownを送信します。",
                file=discord.File(
                    fp=BytesIO(translated_md.encode("utf-8")), filename="japanese.md"
                ),
            )

        # summary
        elif attachment.filename.endswith(".md") and (
            message.content == "summary" or message.content == "slide"
        ):
            md_bytes = await attachment.read()
            print(f"Received Markdown file: {attachment.filename}")

            await message.channel.send(
                "Markdownファイルを受け付けました。要約を開始します。"
            )

            md_content = md_bytes.decode("utf-8")

            type = "ja_summary" if message.content == "summary" else "en_slide"
            output = await client.loop.run_in_executor(
                None, self.summarize_markdown, md_content, type
            )

            await message.channel.send(
                "要約が完了しました。",
                file=discord.File(
                    fp=BytesIO(output.encode("utf-8")), filename="result.md"
                ),
            )
        # markdown to html
        elif attachment.filename.endswith(".md") and message.content == "html":
            md_bytes = await attachment.read()
            print(f"Received Markdown file: {attachment.filename}")

            await message.channel.send(
                "Markdownファイルを受け付けました。HTMLに変換します。"
            )

            md_content = md_bytes.decode("utf-8")

            html_content = convert_markdown(md_content)

            await message.channel.send(
                "HTMLに変換が完了しました。",
                file=discord.File(
                    fp=BytesIO(html_content.encode("utf-8")), filename="result.html"
                ),
            )


intents = discord.Intents.default()
intents.message_content = True

client = PaperBot(intents=intents)
client.run(os.getenv("DISCORD_TOKEN"))
