// One overlay outside the scrolling, masked columns keeps film stills unclipped.
const filmPreview = document.createElement('figure');
filmPreview.className = 'film-preview';
filmPreview.hidden = true;
const filmPreviewCaption = document.createElement('figcaption');
const filmPreviewImage = document.createElement('img');
filmPreviewImage.alt = '';
filmPreviewImage.setAttribute('aria-hidden', 'true');
filmPreviewImage.decoding = 'async';
filmPreviewImage.draggable = false;
filmPreview.append(filmPreviewCaption, filmPreviewImage);
document.body.append(filmPreview);
let activeScreening = null;
let previewRequest = 0;
let previewImage = null;
let previewSummary = '';
function layoutFilmCaption(){
  const words=previewSummary.trim().split(/\s+/);
  let lines=['',''], best=Infinity;
  for(let i=1;i<words.length;i++){
    const pair=[words.slice(0,i).join(' '),words.slice(i).join(' ')];
    const score=Math.max(...pair.map(line=>line.length));
    if(score<best){best=score;lines=pair;}
  }
  filmPreviewCaption.replaceChildren(...lines.map(text=>{
    const line=document.createElement('span');line.textContent=text;return line;
  }));
}
function hideFilmPreview(){previewRequest++;filmPreview.hidden=true;activeScreening=null;previewImage=null;}
function positionFilmPreview(){
  if(!activeScreening?.isConnected||!previewImage)return;
  const rect=activeScreening.getBoundingClientRect();
  const ratio=previewImage.naturalWidth/previewImage.naturalHeight;
  const width=Math.min(360,innerWidth-24);
  filmPreview.style.width=`${width}px`;
  filmPreviewImage.style.width=`${width}px`;
  filmPreviewImage.style.height=`${width/ratio}px`;
  filmPreview.style.left=`${Math.max(12,Math.min(rect.left-27,innerWidth-width-12))}px`;
  filmPreview.style.top='0px';
  filmPreview.hidden=false;
  const height=filmPreview.getBoundingClientRect().height;
  if(rect.top-height-8<8){filmPreview.hidden=true;return;}
  filmPreview.style.top=`${rect.top-height-8}px`;
}
function showFilmPreview(screening,film){
  hideFilmPreview();const url=film.imageUrl;
  if(!url||!(url.startsWith('stills/')||/^https?:\/\//.test(url)))return;
  activeScreening=screening;const request=previewRequest;const image=new Image();
  image.onload=()=>{if(request!==previewRequest||activeScreening!==screening)return;previewImage=image;filmPreviewImage.src=image.src;previewSummary=state.filmSummaries[film.title]||'';filmPreviewCaption.hidden=!previewSummary;layoutFilmCaption();positionFilmPreview();};
  image.onerror=()=>{if(request===previewRequest)hideFilmPreview();};image.src=url;
}
function bindFilmPreview(screening,film){
  screening.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')showFilmPreview(screening,film)});
  screening.addEventListener('pointerleave',()=>{if(screening.matches(':focus-visible'))showFilmPreview(screening,film);else if(activeScreening===screening)hideFilmPreview()});
  screening.addEventListener('focus',()=>{if(screening.matches(':focus-visible'))showFilmPreview(screening,film)});
  screening.addEventListener('blur',()=>{if(activeScreening===screening)hideFilmPreview()});
}
document.addEventListener('scroll',hideFilmPreview,true);window.addEventListener('resize',hideFilmPreview);document.addEventListener('keydown',event=>{if(event.key==='Escape')hideFilmPreview()});window.addEventListener('blur',hideFilmPreview);
