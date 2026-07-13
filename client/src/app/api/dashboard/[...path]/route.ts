import { NextResponse } from 'next/server';

/**
 * Proxy dashboard API calls to the bot server, deriving its origin from
 * BOT_START_URL (same variable the /api/start proxy uses).
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const botStartUrl =
    process.env.BOT_START_URL || 'http://localhost:7860/start';
  const botOrigin = new URL(botStartUrl).origin;

  const { path } = await params;
  const url = `${botOrigin}/api/dashboard/${path.join('/')}`;

  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Bot server responded ${response.status}`);
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      { error: `Failed to reach bot server: ${error}` },
      { status: 502 }
    );
  }
}
