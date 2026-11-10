// 2D 脸：戏台和灵眸总控共用。页面要提供全局 M（含 rest、flags）
const $=i=>document.getElementById(i);let skinNow="";
const FACE_SVG=`<svg id="face" viewBox="-200 -225 400 450" role="img" aria-label="灵眸的表情">
<defs><clipPath id="cl"><path id="eyeShapeL"/></clipPath><clipPath id="cr"><path id="eyeShapeR"/></clipPath><clipPath id="cm"><path id="mclip"/></clipPath></defs>
<g id="skin"></g><g id="eyeL"></g><g id="eyeR"></g>
<line id="browL" stroke-width="12" stroke-linecap="round"/><line id="browR" stroke-width="12" stroke-linecap="round"/>
<path id="mouth" fill="var(--mouth)"/><g clip-path="url(#cm)"><ellipse id="tongue" cx="0" rx="30" ry="15" fill="var(--tongue)"/></g>
<path id="lipU" fill="none" stroke="var(--lip)" stroke-width="7" stroke-linecap="round"/><path id="lipL" fill="none" stroke="var(--lip)" stroke-width="7" stroke-linecap="round"/>
</svg>`;
const SK={red:{f:"#b8352b",b:"#1a1110",p:`<path d="M-54-210Q0-160 54-210L30-130L0-100L-30-130Z" fill="#7c1f19"/><path d="M-160-30Q-100 10-112-120L-40-112Q-64-10-160-30ZM160-30Q100 10 112-120L40-112Q64-10 160-30Z" fill="#1a1110" opacity=".85"/>`},
black:{f:"#26221f",b:"#f5efe2",p:`<path d="M0-208L26-120L0-92L-26-120Z" fill="#f5efe2"/><path d="M-158-20Q-96-16-108-122L-44-108Q-50 10-158-20ZM158-20Q96-16 108-122L44-108Q50 10 158-20Z" fill="#f5efe2" opacity=".92"/>`},
white:{f:"#f1ece1",b:"#1b1b1f",p:`<path d="M-120-46Q-72-90-28-44M120-46Q72-90 28-44" stroke="#1b1b1f" stroke-width="5" fill="none"/><path d="M-20 20L-46 70M20 20L46 70" stroke="#6b6358" stroke-width="3" fill="none"/>`},
blue:{f:"#2c5d9b",b:"#111",p:`<path d="M0-210L34-120L0-80L-34-120Z" fill="#e4dcc9"/><path d="M-160-20Q-94-20-104-124L-44-108Q-50 0-160-20ZM160-20Q94-20 104-124L44-108Q50 0 160-20Z" fill="#111" opacity=".85"/>`},
gold:{f:"#c9a03f",b:"#3a2a0c",p:`<path d="M0-208L22-140L0-112L-22-140Z" fill="#fbeab0"/><circle cx="0" cy="-160" r="9" fill="#a8281e"/>`},
dan:{f:"#f6e7dc",b:"#2a1d1c",p:`<ellipse cx="-74" cy="-14" rx="64" ry="60" fill="#e8848c" opacity=".55"/><ellipse cx="74" cy="-14" rx="64" ry="60" fill="#e8848c" opacity=".55"/>`},
chou:{f:"#ecd6bd",b:"#1f1712",p:`<path d="M-30-52H30V24H-30Z" fill="#fff" stroke="#b9ab97" stroke-width="2"/>`},
robot:{f:"#d8dce1",b:"#2b3038",p:`<path d="M-168-40H168" stroke="#00000012" stroke-width="2"/>`},
anime:{f:"#fbe8d7",b:"#5a3a2a",p:`<ellipse cx="-96" cy="28" rx="26" ry="11" fill="#f2a0a0" opacity=".55"/><ellipse cx="96" cy="28" rx="26" ry="11" fill="#f2a0a0" opacity=".55"/>`}};
const HEAD="M0-212C112-212 168-138 168-40C168 66 112 196 0 212C-112 196-168 66-168-40C-168-138-112-212 0-212Z";
function skin(n){if(n===skinNow)return;skinNow=n;const s=SK[n];const big=n==="anime",rx=big?54:42,ry=big?46:29,ey=big?-30:-42;
 $("skin").innerHTML=`<path d="${HEAD}" fill="${s.f}" stroke="#00000055" stroke-width="3"/>${s.p}`;
 for(const[id,x,sh,cl]of[["eyeL",-72,"eyeShapeL","cl"],["eyeR",72,"eyeShapeR","cr"]]){
  const d=`M${x-rx} ${ey}a${rx} ${ry} 0 1 0 ${2*rx} 0a${rx} ${ry} 0 1 0 ${-2*rx} 0Z`;$(sh).setAttribute("d",d);
  const r=big?32:19,pr=big?18:9;
  $(id).dataset.ey=ey;$(id).dataset.h=2*ry;
  $(id).innerHTML=`<g clip-path="url(#${cl})"><rect x="${x-rx-4}" y="${ey-ry-4}" width="${2*rx+8}" height="${2*ry+8}" fill="var(--white)"/>
  <g class="ball"><circle cx="${x}" cy="${ey}" r="${r}" fill="${big?"#3b6fb0":"var(--iris)"}"/><circle cx="${x}" cy="${ey}" r="${pr}" fill="var(--pupil)"/>${big?`<circle cx="${x-11}" cy="${ey-13}" r="9" fill="#fff"/><circle cx="${x+12}" cy="${ey+12}" r="4" fill="#fff"/>`:""}</g>
  <rect class="top" x="${x-rx-4}" y="${ey-3*ry}" width="${2*rx+8}" height="${2*ry+2}" fill="${s.f}"/><rect class="bot" x="${x-rx-4}" y="${ey+ry}" width="${2*rx+8}" height="${2*ry}" fill="${s.f}"/></g>
  <path d="${d}" fill="none" stroke="${s.b}" stroke-width="${big?5:3.5}"/>`}
 $("browL").setAttribute("stroke",s.b);$("browR").setAttribute("stroke",s.b)}
function brow(el,x,i,o,sg){const y=v=>-108-52*(v-.5);el.setAttribute("x1",x-sg*38);el.setAttribute("x2",x+sg*38);el.setAttribute("y1",y(i));el.setAttribute("y2",y(o))}
function draw(u){const f=M.flags,d=n=>u[n]-M.rest[n],eL=f.eye_l_robot_left?1:-1,sg=f.lr_up_robot_left?1:-1,big=skinNow==="anime",gx=d("LR")*2*sg*(big?20:22),gy=-d("UD")*2*(big?12:13);
 for(const[side,id,x]of[["L",eL>0?"eyeR":"eyeL",72*eL],["R",eL>0?"eyeL":"eyeR",-72*eL]]){const g=$(id),h=+g.dataset.h;
  g.querySelector(".ball").setAttribute("transform",`translate(${gx} ${gy})`);
  g.querySelector(".top").setAttribute("transform",`translate(0 ${(1-u["T"+side])*h*.62})`);
  g.querySelector(".bot").setAttribute("transform",`translate(0 ${-(1-u["B"+side])*h*.42})`);
  brow($(side==="L"?(eL>0?"browR":"browL"):(eL>0?"browL":"browR")),x,u[side+"I"],u[side+"O"],Math.sign(x))}
 const V=(a,b)=>f.mouth_l_robot_left?[b,a]:[a,b],[cuA,cuB]=V(d("CUL"),d("CUR")),[clA,clB]=V(d("CLL"),d("CLR")),[luA,luB]=V(d("LUL"),d("LUR")),[llA,llB]=V(d("LLL"),d("LLR"));
 const jaw=(u.JL+u.JR)/2,y0=112,xa=-62-clA*40,xb=62+clB*40,ya=y0-cuA*50,yb=y0-cuB*50,up=v=>y0-6-v*42,lo=v=>y0+6+jaw*76-v*28;
 const U=`M${xa} ${ya}C${xa*.45} ${up(luA)} ${xb*.45} ${up(luB)} ${xb} ${yb}`,L=`C${xb*.45} ${lo(llB)} ${xa*.45} ${lo(llA)} ${xa} ${ya}`;
 $("mouth").setAttribute("d",U+L+"Z");$("mclip").setAttribute("d",U+L+"Z");$("lipU").setAttribute("d",U);$("lipL").setAttribute("d",`M${xb} ${yb}`+L);
 $("tongue").setAttribute("cy",y0+10+jaw*66-u.TON*22)}
