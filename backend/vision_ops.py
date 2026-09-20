"""Native detector geometry and one-to-one agreement across independent branches."""
import copy
import math
import cv2
import numpy as np
import zxingcpp
from . import cimg_native
from .timelines import Frame

def reference_image(source,shape):
    h,w=shape[:2]
    return cv2.resize(source,(w,h),interpolation=cv2.INTER_AREA) if source.shape[:2]!=(h,w) else source

def paint_region(mask,region):
    kind,data=region
    if kind=='pixels':mask.flat[data]=255
    elif kind=='circle':cv2.circle(mask,(data[0],data[1]),data[2],255,cv2.FILLED)
    elif kind=='line':cv2.line(mask,tuple(data[:2]),tuple(data[2:]),255,1)
    else:cv2.fillPoly(mask,[np.asarray(data,np.int32)],255)

def assemble(shape,source,measures,items,basis,extra=None,reference=None):
    h,w=shape[:2];mask=np.zeros((h,w),np.uint8);preview=(reference if reference is not None else reference_image(source,shape)).copy()
    items.sort(key=lambda item:(item[0]['box'][1],item[0]['box'][0]))
    for detection,region in items:
        paint_region(mask,region)
        x,y,bw,bh=detection['normalized_box'];cv2.rectangle(preview,(round(x*w),round(y*h)),(round((x+bw)*w),round((y+bh)*h)),(60,136,55),2)
    return Frame(mask,'mask',preview,{'detections':[d for d,r in items],'count':len(items),'unit':measures.unit if measures.pixels_per_unit else 'px','measurement_basis':basis,**(extra or {})},[r for d,r in items])

def record(box,shape,source,measures,region,*,length=None,width=None,area=None,center=None,angle=None,extra=None,reference=None):
    h,w=shape[:2];sx,sy=source.shape[1]/w,source.shape[0]/h;x,y,bw,bh=box;div=measures.pixels_per_unit or 1
    values={};round3=lambda v:None if v is None else round(float(v),3)
    for key,value in [('length',length),('width',width),('area',area)]:
        if key in measures.fields:values[key]=round3(value/(div*div if key=='area' else div)) if value is not None else None
    if 'center' in measures.fields:values['center_px']=[round3(c) for c in center] if center is not None else None
    if 'angle' in measures.fields:values['angle_deg']=round3(angle)
    if 'color' in measures.fields:
        left,top=max(0,int(x)),max(0,int(y));right,bottom=min(w,int(x+bw)),min(h,int(y+bh))
        mask=np.zeros((bottom-top,right-left),np.uint8);kind,data=region
        if kind=='pixels':
            yy,xx=np.divmod(data,w);mask[yy-top,xx-left]=255
        elif kind=='circle':paint_region(mask,(kind,(data[0]-left,data[1]-top,data[2])))
        elif kind=='line':paint_region(mask,(kind,(data[0]-left,data[1]-top,data[2]-left,data[3]-top)))
        else:paint_region(mask,(kind,np.asarray(data)-np.array([left,top])))
        b,g,r,_=cv2.mean((reference if reference is not None else reference_image(source,shape))[top:bottom,left:right],mask=mask);values['mean_rgb']=[int(c+.5) for c in (r,g,b)]
    values.update(extra or {})
    return {'box':[round3(v) for v in (x*sx,y*sy,bw*sx,bh*sy)],'normalized_box':[x/w,y/h,bw/w,bh/h],'measurements':values}

def apply_extended(frame,op,source,measures):
    im=frame.image;p=op.params;k=op.kind;h,w=im.shape[:2];sx,sy=source.shape[1]/w,source.shape[0]/h;items=[]
    if k=='cimg_distance':
        out,maximum=cimg_native.distance(im,p)
        return Frame(out,'gray',details={'max_distance_px':round(maximum,3),'pixels_per_level':p['pixels_per_level']})
    ref=reference_image(source,im.shape)
    if k=='cimg_components':
        out,labels,count=cimg_native.components(im,p)
        # Membership is retained for confirmation, including holes and diagonal connections.
        flat=labels.ravel();positions=np.flatnonzero(flat);order=np.argsort(flat[positions],kind='stable');positions=positions[order]
        groups=np.split(positions,np.flatnonzero(np.diff(flat[positions]))+1) if positions.size else []
        for pixels in groups:
            ys,xs=np.divmod(pixels,w);x,y=int(xs.min()),int(ys.min());bw,bh=int(xs.max())-x+1,int(ys.max())-y+1
            region=('pixels',pixels);a,b=bw*sx,bh*sy
            d=record((x,y,bw,bh),im.shape,source,measures,region,reference=ref,length=max(a,b),width=min(a,b),area=len(pixels)*sx*sy,center=((x+bw/2)*sx,(y+bh/2)*sy),angle=None if max(a,b)/min(a,b)<=1.05 else (0 if a>=b else 90))
            items.append((d,region))
        return assemble(im.shape,source,measures,items,'Connected foreground pixels; holes excluded; axis-aligned extents',reference=ref)
    if k=='hough_circles':
        if h*w>262_144:raise ValueError('Circle detection supports at most 262,144 pixels. Add Resize with max side 512 before this step.')
        edges=cv2.Canny(im,p['edge_threshold']/2,p['edge_threshold'])
        edge_count=cv2.countNonZero(edges)
        if edge_count>25_000 or edge_count*p['max_radius']>500_000:
            raise ValueError('Circle search is too broad for these edges. Reduce maximum radius, denoise, or resize first.')
        circles=cv2.HoughCircles(im,cv2.HOUGH_GRADIENT,1,p['min_distance'],param1=p['edge_threshold'],param2=p['votes'],minRadius=p['min_radius'],maxRadius=p['max_radius'])
        if circles is not None:
            if len(circles[0])>256:raise ValueError('More than 256 circles. Increase votes or minimum spacing.')
            for cx,cy,r in circles[0]:
                cx,cy,r=map(float,(cx,cy,r));region=('circle',(int(cx+.5),int(cy+.5),int(r+.5)))
                x,y=max(0,math.floor(cx-r)),max(0,math.floor(cy-r));right,bottom=min(w,math.ceil(cx+r)+1),min(h,math.ceil(cy+r)+1)
                d=record((x,y,right-x,bottom-y),im.shape,source,measures,region,reference=ref,length=2*r*max(sx,sy),width=2*r*min(sx,sy),area=math.pi*r*r*sx*sy,center=(cx*sx,cy*sy),extra={'radius_px':round(r*math.sqrt(sx*sy),3)})
                items.append((d,region))
        return assemble(im.shape,source,measures,items,'Fitted circles; dimensions describe the fitted disk, including any clipped extent',reference=ref)
    if k=='hough_lines':
        lines=cv2.HoughLinesP(im,1,np.pi/180,p['votes'],minLineLength=p['min_length'],maxLineGap=p['max_gap'])
        if lines is not None:
            if len(lines)>1000:raise ValueError('More than 1,000 line segments. Increase votes or minimum length.')
            for line in np.asarray(lines).reshape(-1,4):
                x1,y1,x2,y2=map(int,line);region=('line',(x1,y1,x2,y2));dx,dy=(x2-x1)*sx,(y2-y1)*sy
                d=record((min(x1,x2),min(y1,y2),abs(x2-x1)+1,abs(y2-y1)+1),im.shape,source,measures,region,reference=ref,length=math.hypot(dx,dy),center=((x1+x2)*sx/2,(y1+y2)*sy/2),angle=math.degrees(math.atan2(dy,dx))%180,extra={'endpoints_px':[round(v,3) for v in (x1*sx,y1*sy,x2*sx,y2*sy)]})
                items.append((d,region))
        return assemble(im.shape,source,measures,items,'Line endpoint distance and orientation; width and area are undefined; color samples the 1-pixel segment',reference=ref)
    if k=='barcode':
        formats={'all':zxingcpp.BarcodeFormat.NONE,'qr':zxingcpp.BarcodeFormat.QRCode,'linear':zxingcpp.BarcodeFormat.LinearCodes,'data_matrix':zxingcpp.BarcodeFormat.DataMatrix}[p['formats']]
        codes=zxingcpp.read_barcodes(im,formats=formats,try_rotate=p['try_rotate'],try_downscale=p['try_downscale'],text_mode=zxingcpp.TextMode.Plain,binarizer={'local_average':zxingcpp.Binarizer.LocalAverage,'global_histogram':zxingcpp.Binarizer.GlobalHistogram,'fixed_threshold':zxingcpp.Binarizer.FixedThreshold}[p['binarizer']],is_pure=False,return_errors=False)
        for code in codes:
            corners=[code.position.top_left,code.position.top_right,code.position.bottom_right,code.position.bottom_left]
            points=np.array([(v.x,v.y) for v in corners],np.int32);region=('polygon',points);x,y,bw,bh=cv2.boundingRect(points)
            original=points.astype(np.float32)*np.array([sx,sy],np.float32);(cx,cy),(rw,rh),angle=cv2.minAreaRect(original)
            d=record((x,y,bw,bh),im.shape,source,measures,region,reference=ref,length=max(rw,rh),width=min(rw,rh),area=cv2.contourArea(original),center=(cx,cy),angle=None if max(rw,rh)/max(min(rw,rh),1e-9)<=1.05 else (angle+(90 if rw<rh else 0))%180,extra={'text':code.text,'format':code.format.name})
            items.append((d,region))
        return assemble(im.shape,source,measures,items,'Decoded code quadrilateral; dimensions describe the code, not its surrounding object',reference=ref)
    raise ValueError('Confirmation requires completed supporting pipelines')

def overlap(a,b):
    x,y,w,h=a;xx,yy,ww,hh=b
    intersection=max(0,min(x+w,xx+ww)-max(x,xx))*max(0,min(y+h,yy+hh)-max(y,yy))
    return intersection/max(w*h+ww*hh-intersection,1e-12)

def confirm_frame(primary,supports,params,source,measures):
    detections=primary.details.get('detections')
    if detections is None:raise ValueError('Confirmation must immediately follow an object detector')
    if len(primary.regions)!=len(detections):raise ValueError('Primary object membership is unavailable')
    if not supports or params['min_support']>len(supports):raise ValueError('Choose enough supporting detector pipelines for the required agreement')
    comparisons=len(detections)*sum(len(support.details.get('detections',[])) for _,support in supports)
    if comparisons>250_000:raise ValueError('Confirmation needs fewer candidate objects. Tighten upstream detector filters (at most 250,000 pair comparisons).')
    votes=[[] for _ in detections]
    for name,support in supports:
        others=support.details.get('detections')
        if others is None:raise ValueError('Every supporting pipeline must finish with an object detector')
        pairs=[]
        for i,a in enumerate(detections):
            for j,b in enumerate(others):
                if params['match_text'] and (not a['measurements'].get('text') or a['measurements'].get('text')!=b['measurements'].get('text')):continue
                score=overlap(a['normalized_box'],b['normalized_box'])
                if score>=params['iou']:pairs.append((-score,i,j))
        used_primary=set();used_support=set()
        for _,i,j in sorted(pairs):
            if i not in used_primary and j not in used_support:
                votes[i].append(name);used_primary.add(i);used_support.add(j)
    items=[]
    for i,d in enumerate(detections):
        if len(votes[i])>=params['min_support']:
            d=copy.deepcopy(d);d['measurements']['supporting_branches']=len(votes[i]);items.append((d,primary.regions[i]))
    return assemble(primary.image.shape,source,measures,items,primary.details.get('measurement_basis','Primary detector measurements'),{'agreement':{'primary_count':len(detections),'kept':len(items),'rejected':len(detections)-len(items),'required':params['min_support'],'supporting_pipelines':[name for name,_ in supports]}})
