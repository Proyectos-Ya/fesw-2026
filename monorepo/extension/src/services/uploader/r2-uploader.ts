export class R2Uploader {
  public static async calculateSha256(data: ArrayBuffer): Promise<string> {
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  public static async uploadToR2(
    putUrl: string,
    fileBytes: ArrayBuffer,
    headers: Record<string, string>
  ): Promise<void> {
    const response = await fetch(putUrl, {
      method: "PUT",
      headers: {
        ...headers,
        "Content-Type": headers["Content-Type"] || "application/octet-stream",
      },
      body: fileBytes,
    });

    if (!response.ok) {
      throw new Error(
        `Error en subida directa a R2: ${response.status} ${response.statusText}`
      );
    }
  }
}
