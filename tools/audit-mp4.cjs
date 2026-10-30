// Offline check of the recommended H.264/AAC upload profile, not a YouTube acceptance test.
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
const [file,expectedArg,orientation]=process.argv.slice(2);
if(!file){console.error('Usage: node tools/audit-mp4.cjs VIDEO [EXPECTED_SECONDS] [vertical|horizontal]');process.exit(2);}
function run(command,args){const r=spawnSync(command,args,{encoding:'utf8',maxBuffer:8*1024*1024});if(r.error)throw r.error;if(r.status!==0)throw Error(r.stderr||command+' failed');return r.stdout;}
function boxes(path){const fd=fs.openSync(path,'r'),out=[];try{const size=fs.fstatSync(fd).size;let offset=0;while(offset+8<=size){const b=Buffer.alloc(16);fs.readSync(fd,b,0,Math.min(16,size-offset),offset);let n=b.readUInt32BE(0);if(n===1){const extended=b.readBigUInt64BE(8);if(extended>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Box too large');n=Number(extended);}if(n===0)n=size-offset;if(n<8||offset+n>size)throw Error('Invalid MP4 box');out.push({type:b.toString('ascii',4,8),offset});offset+=n;}return out;}finally{fs.closeSync(fd);}}
try{
 const probe=JSON.parse(run('ffprobe',['-v','error','-show_format','-show_streams','-of','json',file]));
 const video=probe.streams.filter(s=>s.codec_type==='video'),audio=probe.streams.filter(s=>s.codec_type==='audio');
 const duration=Number(probe.format.duration),expected=expectedArg===undefined?null:Number(expectedArg);
 if(expected!==null&&(!Number.isFinite(expected)||expected<=0))throw Error('Expected duration must be positive');
 if(orientation&&!['vertical','horizontal'].includes(orientation))throw Error('Unknown orientation');
 const b=boxes(file),moov=b.find(x=>x.type==='moov'),mdat=b.find(x=>x.type==='mdat');
 const checks={mp4:probe.format.format_name.split(',').includes('mp4'),h264:video.length===1&&video[0].codec_name==='h264',yuv420p:video[0]?.pix_fmt==='yuv420p',aac:audio.length===1&&audio[0].codec_name==='aac',duration:Number.isFinite(duration)&&duration>0,durationMatches:expected===null?null:Math.abs(duration-expected)<=.15,faststart:!!moov&&!!mdat&&moov.offset<mdat.offset,orientation:!orientation?null:orientation==='vertical'?video[0]?.height>video[0]?.width:video[0]?.width>video[0]?.height};
 run('ffmpeg',['-v','error','-xerror','-i',file,'-map','0:v:0','-map','0:a:0','-f','null','-']);checks.fullDecode=true;
 const result={file,duration,expected,video:video.map(({codec_name,width,height,pix_fmt,avg_frame_rate})=>({codec_name,width,height,pix_fmt,avg_frame_rate})),audio:audio.map(({codec_name,sample_rate,channels})=>({codec_name,sample_rate,channels})),checks,passed:Object.values(checks).every(v=>v!==false)};
 console.log(JSON.stringify(result,null,2));if(!result.passed)process.exitCode=1;
}catch(e){console.error(e.message);process.exitCode=2;}
