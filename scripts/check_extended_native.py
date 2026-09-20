"""Compile actual export bundles; compare pixels, geometry, identity and dependency order."""
import io,json,os,subprocess,sys,zipfile
from pathlib import Path
import cv2,numpy as np,zxingcpp
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.models import Measurements
from backend.timelines import Frame,Operation,Timeline,execution_plan,resolve_paths,apply_operation
from backend.vision_ops import confirm_frame
from backend.vision_params import supporting_ids
from backend.timeline_exporter import TimelineExportRequest,export_timeline
DEST=ROOT/'artifacts/expanded-native';DEST.mkdir(parents=True,exist_ok=True)
M=Measurements(fields=['length','width','area','angle','center','color'],pixels_per_unit=2,unit='mm')
def op(kind,id=None,**params):return Operation(id=id or kind,kind=kind,params=params)
def root(ops):return [Timeline(id='main',name='Native check',operations=ops)]
a=np.zeros((100,140,3),np.uint8);a[10:35,10:45]=255;a[15:22,17:23]=0;a[50:70,75:100]=255
circles=np.full((240,320,3),255,np.uint8);cv2.circle(circles,(90,110),35,(0,0,0),3);cv2.circle(circles,(205,110),25,(0,0,0),3)
lines=np.zeros((100,160,3),np.uint8);cv2.line(lines,(20,45),(130,45),(255,255,255),1)
qr=np.asarray(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode,'Contour <tag> & café',width=180,height=180,quiet_zone=12));qr=cv2.cvtColor(qr,cv2.COLOR_GRAY2BGR)
objects=np.full((160,240,3),255,np.uint8);objects[30:80,25:75]=(0,0,200);objects[40:100,135:195]=(180,0,0)
confirmation=[Timeline(id='main',name='Primary',operations=[op('resize'),op('grayscale'),op('threshold',value=220),op('invert'),op('cimg_components','objects'),op('confirm','agreement',pipeline_ids='color')]),Timeline(id='color',name='Color support',parent_id='main',fork_after='resize',operations=[op('resize','smaller',max_side=128),op('hsv_mask'),op('contours','red')])]
cases=[('regions',a,root([op('grayscale'),op('threshold'),op('cimg_components',min_pixels=1)])),('distance',a,root([op('grayscale'),op('threshold'),op('cimg_distance',pixels_per_level=.5)])),('circles',circles,root([op('grayscale'),op('hough_circles',min_radius=20,max_radius=40,votes=25,min_distance=60)])),('lines',lines,root([op('grayscale'),op('threshold'),op('hough_lines',votes=20,min_length=70,max_gap=2)])),('barcode',qr,root([op('barcode')])),('confirmation',objects,confirmation)]
ramp=np.tile(np.linspace(10,200,160).astype(np.uint8),(100,1));ramp[25:40,25:40]=245;ramp[60:75,100:115]=3
ramp=cv2.cvtColor(ramp,cv2.COLOR_GRAY2BGR)
for kind in ['top_hat','black_hat','sobel','range_mask','morph_gradient','gamma','fill_holes']:
    source=a if kind in ('fill_holes','morph_gradient') else ramp
    operations=[op('grayscale')]
    if kind in ('fill_holes','morph_gradient'):operations.append(op('threshold'))
    operations.append(op(kind,**({'gamma':.7} if kind=='gamma' else {})))
    cases.append((kind,source,root(operations)))
if len(sys.argv)>1:cases=[case for case in cases if case[0] in sys.argv[1:]]
env=os.environ.copy();env['ZIG_GLOBAL_CACHE_DIR']=str(ROOT/'.tools/zig-cache');env['ZIG_LOCAL_CACHE_DIR']=str(ROOT/'.tools/zig-local-cache')
cmake=ROOT/'.venv/Lib/site-packages/cmake/data/bin/cmake.exe';records=[]
for name,source,graphs in cases:
    directory=DEST/name;directory.mkdir(exist_ok=True);image=directory/'input.png';cv2.imwrite(str(image),source)
    package=export_timeline(TimelineExportRequest(timelines=graphs,selected_timeline_id='main',measurements=M));(directory/'download.zip').write_bytes(package)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        for info in archive.infolist():
            if info.is_dir():continue
            target=directory/info.filename;target.parent.mkdir(parents=True,exist_ok=True);data=archive.read(info)
            if not target.exists() or target.read_bytes()!=data:target.write_bytes(data)
    args=[str(cmake),'-S',str(directory),'-B',str(directory/'build'),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',f'-DCMAKE_MAKE_PROGRAM={(ROOT/".venv/Scripts/ninja.exe").as_posix()}',f'-DCMAKE_CXX_COMPILER={(ROOT/".tools/cxx.cmd").as_posix()}',f'-DCMAKE_C_COMPILER={(ROOT/".tools/cc.cmd").as_posix()}',f'-DCMAKE_AR={(ROOT/".tools/ar.cmd").as_posix()}',f'-DCMAKE_RANLIB={(ROOT/".tools/ranlib.cmd").as_posix()}',f'-DOpenCV_DIR={(ROOT/".tools/opencv-build").as_posix()}']
    subprocess.run(args,env=env,check=True);subprocess.run([str(cmake),'--build',str(directory/'build'),'--parallel','2'],env=env,check=True)
    output=directory/'final.png';binary=directory/'build/detector.exe';actual=json.loads(subprocess.check_output([str(binary),'--output',str(output),str(image)],text=True,encoding='utf-8',env=env))
    order,previous,_=execution_plan(graphs,'main');resolved=resolve_paths(graphs);frames={'source':Frame(source,'color')};expected=[]
    for operation in order:
        frame=confirm_frame(frames[previous[operation.id]],[(tid,frames[resolved[tid][-1].id]) for tid in supporting_ids(operation)],operation.params,source,M) if operation.kind=='confirm' else apply_operation(frames[previous[operation.id]],operation,source,M)
        frames[operation.id]=frame
        if 'detections' in frame.details:expected.append((operation.id,frame.details))
    final=frames[resolved['main'][-1].id];pixels=cv2.imread(str(output),cv2.IMREAD_UNCHANGED)
    assert pixels.shape==final.image.shape,(name,'shape');differences=int(np.count_nonzero(pixels!=final.image));assert not differences,(name,'final pixels',differences)
    assert [s['id'] for s in actual['operations']]==[operation.id for operation in order],(name,'dependency order')
    assert len(actual['measurement_steps'])==len(expected)
    for native,(id,python) in zip(actual['measurement_steps'],expected):
        assert native['id']==id and native['count']==python['count'],(name,id,'count',native['count'],python['count'])
        for a,b in zip(native['detections'],python['detections']):
            assert np.allclose(a['box'],b['box'],atol=.002,rtol=0),(name,id,'box',a,b)
            assert a['measurements'].keys()==b['measurements'].keys(),(name,id,'fields',a,b)
            for key,value in b['measurements'].items():
                if isinstance(value,str) or value is None:assert a['measurements'][key]==value,(name,id,key,a,b)
                else:assert np.allclose(a['measurements'][key],value,atol=.02,rtol=0),(name,id,key,a,b)
    identity_cases=[]
    if name=='barcode':
        for format,text in [(zxingcpp.BarcodeFormat.EAN13,'5901234123457'),(zxingcpp.BarcodeFormat.UPCA,'036000291452'),(zxingcpp.BarcodeFormat.Code128,'CONTOUR-42'),(zxingcpp.BarcodeFormat.DataMatrix,'Contour 2D')]:
            test=np.asarray(zxingcpp.write_barcode(format,text,width=320,height=100,quiet_zone=12));test=cv2.cvtColor(test,cv2.COLOR_GRAY2BGR);testpath=directory/f'{format.name}.png';cv2.imwrite(str(testpath),test)
            identity_output=directory/f'{format.name}-final.png'
            native=json.loads(subprocess.check_output([str(binary),'--output',str(identity_output),str(testpath)],text=True,encoding='utf-8',env=env));python=apply_operation(Frame(test,'color'),op('barcode'),test,M)
            assert native['measurement_steps'][0]['count']==python.details['count']==1
            observed=native['measurement_steps'][0]['detections'][0];truth=python.details['detections'][0]
            assert observed['measurements']['text']==truth['measurements']['text'] and observed['measurements']['format']==truth['measurements']['format']
            assert not np.count_nonzero(cv2.imread(str(identity_output),cv2.IMREAD_UNCHANGED)!=python.image)
            assert np.allclose(observed['box'],truth['box'],atol=.002,rtol=0)
            identity_cases.append({'requested_format':format.name,'decoded_format':truth['measurements']['format'],'text':truth['measurements']['text'],'pixel_differences':0})
    record={'case':name,'passed':True,'pixel_differences':differences,'measurement_steps':len(expected),'final_count':final.details.get('count'),'operation_order':[o.id for o in order],'binary_bytes':binary.stat().st_size,'single_native_ms':actual['latency_ms'],'identity_cases':identity_cases};records.append(record);print(json.dumps(record),flush=True)
    (directory/'parity.json').write_text(json.dumps(record,indent=2))
(DEST/'latest-run.json').write_text(json.dumps(records,indent=2))
