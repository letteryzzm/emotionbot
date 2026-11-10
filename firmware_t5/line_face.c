#include <stdint.h>
#include "line_face.h"

typedef struct {
    uint8_t count;
    lv_point_precise_t points[9];
} Stroke;

#define S2(a,b,c,d) {2,{{a,b},{c,d}}}
#define S3(a,b,c,d,e,f) {3,{{a,b},{c,d},{e,f}}}
#define S5(a,b,c,d,e,f,g,h,i,j) {5,{{a,b},{c,d},{e,f},{g,h},{i,j}}}
#define S7(a,b,c,d,e,f,g,h,i,j,k,l,m,n) {7,{{a,b},{c,d},{e,f},{g,h},{i,j},{k,l},{m,n}}}
#define S9(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r) {9,{{a,b},{c,d},{e,f},{g,h},{i,j},{k,l},{m,n},{o,p},{q,r}}}

/* Left brow, right brow, left eye, right eye, mouth on a 288 x 230 artboard. */
static const Stroke faces[7][5] = {
    { S2(43,60,105,60), S2(183,60,245,60),
      S7(45,103,57,92,91,92,105,103,91,114,57,114,45,103),
      S7(183,103,197,92,231,92,243,103,231,114,197,114,183,103),
      S5(89,181,115,183,144,184,173,183,199,181) },
    { S3(44,67,75,57,105,64), S3(183,64,213,57,244,67),
      S5(45,108,60,94,76,89,92,94,106,108),
      S5(182,108,197,94,213,89,229,94,244,108),
      S7(75,166,94,184,120,195,144,198,168,195,194,184,213,166) },
    { S3(43,68,77,56,106,74), S3(182,74,211,56,245,68),
      S5(45,100,60,93,76,94,92,101,106,111),
      S5(182,111,196,101,212,94,228,93,243,100),
      S7(80,195,100,179,120,171,144,168,168,171,188,179,208,195) },
    { S2(43,52,107,79), S2(181,79,245,52),
      S5(46,112,61,103,79,104,95,111,106,118),
      S5(182,118,193,111,209,104,227,103,242,112),
      S5(89,188,115,181,144,179,173,181,199,188) },
    { S3(43,52,76,40,106,50), S3(182,50,212,40,245,52),
      S9(44,102,49,85,63,74,77,70,91,74,103,85,108,102,90,125,62,125),
      S9(180,102,185,85,199,74,213,70,227,74,239,85,244,102,226,125,198,125),
      S9(144,153,163,160,177,180,173,205,144,222,115,205,111,180,125,160,144,153) },
    { S3(43,69,74,44,106,62), S3(182,62,214,44,245,69),
      S7(45,105,55,84,77,77,99,88,106,105,91,123,61,123),
      S7(182,105,189,88,211,77,233,84,243,105,227,123,197,123),
      S7(76,189,98,174,121,185,144,173,167,185,190,174,212,189) },
    { S3(43,57,76,67,106,60), S3(182,70,214,47,245,48),
      S5(45,108,60,103,78,104,94,111,105,113),
      S5(182,113,193,111,210,104,228,103,243,108),
      S7(83,188,110,184,132,179,146,181,160,196,187,197,208,191) }
};

lv_obj_t *line_face_create(lv_obj_t *parent, int emotion)
{
    if (emotion < 0 || emotion >= 7) emotion = 0;
    lv_obj_t *art = lv_obj_create(parent);
    lv_obj_set_size(art, 288, 230);
    lv_obj_set_pos(art, 0, 13);
    lv_obj_set_style_bg_opa(art, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(art, 0, 0);
    lv_obj_set_style_pad_all(art, 0, 0);
    lv_obj_clear_flag(art, LV_OBJ_FLAG_SCROLLABLE);
    for (int i = 0; i < 5; i++) {
        const Stroke *stroke = &faces[emotion][i];
        lv_obj_t *line = lv_line_create(art);
        lv_line_set_points(line, stroke->points, stroke->count);
        lv_obj_set_style_line_width(line, i == 4 ? 6 : 5, 0);
        lv_obj_set_style_line_color(line, lv_color_hex(i == 4 ? 0xFFC8AA : 0xB5F4DE), 0);
        lv_obj_set_style_line_rounded(line, true, 0);
    }
    return art;
}
