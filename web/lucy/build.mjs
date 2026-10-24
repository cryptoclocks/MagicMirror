import {build} from 'esbuild';
import fs from 'node:fs';
for(const [entry,outfile] of [['app.js','studio.bundle.js'],['tracking-worker.js','tracking-worker.bundle.js']]){
  await build({entryPoints:[entry],outfile,bundle:true,format:'iife',platform:'browser',target:'chrome112',minify:true,legalComments:'linked'});
  // Shader template strings from Three.js contain harmless trailing whitespace.
  fs.writeFileSync(outfile,fs.readFileSync(outfile,'utf8').replace(/[\t ]+$/gm,''));
}
