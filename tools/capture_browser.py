"""Optional Three.js-rendered MP4, distinct from the offline Cycles film.
Start npm start first. Requires Playwright/Chromium and FFmpeg.
"""
import argparse,asyncio,subprocess,os
from pathlib import Path
from playwright.async_api import async_playwright
async def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://localhost:5173/?capture');p.add_argument('--output',default='threejs-export.mp4');p.add_argument('--width',type=int,default=1920);p.add_argument('--chromium',default=os.getenv('CHROMIUM'));a=p.parse_args()
    frames=Path('render/browser-frames');frames.mkdir(exist_ok=True,parents=True)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,executable_path=a.chromium,args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--no-sandbox'])
        page=await browser.new_page(viewport={'width':a.width,'height':round(a.width*9/16)},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(a.url);await page.wait_for_function('window.sculpt?.ready === true',timeout=180000)
        await page.evaluate('(w)=>window.sculpt.resize(w,Math.round(w*9/16))',a.width)
        for f in range(528):
            await page.evaluate('(f)=>window.sculpt.renderAt(f)',f)
            await page.locator('canvas').screenshot(path=str(frames/f'{f:05d}.png'))
        await browser.close()
        if errors:raise RuntimeError('\n'.join(errors))
    subprocess.run(['ffmpeg','-y','-framerate','24','-i',str(frames/'%05d.png'),'-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',a.output],check=True)
if __name__=='__main__':asyncio.run(main())
