import fs from "fs";
import path from "path";
import OpenAI from "openai";
import readline from "readline";

const OPENAI_API_KEY = "INSERT_YOUR_OPENAI_KEY";
const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

console.log("Using API key:", OPENAI_API_KEY.slice(0, 10));

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

rl.question("Enter your synthetic dataset prompt: ", async (userPrompt) => {
  try {
    const prompt = `High-quality illustration of a synthetic data task: ${userPrompt}, use theme colors: #111827, #DEFE47, #28B2FB, white`;

    const response = await openai.images.generate({
      model: "dall-e-3",
      prompt,
      n: 1,
      size: "1024x1024",
    });

    const imageUrl = response.data[0].url;
    console.log(`Generated image URL: ${imageUrl}`);

    // Optionally: Save to file
    fs.writeFileSync("image_output.json", JSON.stringify({ prompt: userPrompt, image: imageUrl }, null, 2), "utf-8");

  } catch (error) {
    console.error("Error generating image:", error.message || error);
  } finally {
    rl.close();
  }
});
