/** Vercel CLI: os.hostname() 한글 등 비ASCII 시 HTTP header 오류 방지 */
const os = require("os");
os.hostname = () => "culture-cli";
