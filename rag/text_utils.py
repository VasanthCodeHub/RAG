from langchain_text_splitters import RecursiveCharacterTextSplitter


def text2chunk(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Split the text into chunks of a specified size using LangChain's
    RecursiveCharacterTextSplitter, which splits on a separator hierarchy
    (paragraphs, then lines, then words) so chunks respect natural text
    boundaries instead of cutting mid-sentence.
    - text: str: The text to split into chunks.
    - chunk_size: int: The size of each chunk, in characters.
    - overlap: int: The character overlap between consecutive chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    return splitter.split_text(text)
