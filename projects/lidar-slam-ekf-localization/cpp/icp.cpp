#include <cmath>
#include <limits>
// Align source points to target by repeated nearest-neighbour rigid alignment.
extern "C" int icp(const double* src, int n, const double* dst, int m, double* out, int iterations, double max_distance) {
    if (n < 3 || m < 3 || max_distance <= 0) return -1;
    double x=out[0], y=out[1], theta=out[2];
    for(int iter=0; iter<iterations; ++iter) {
        double sx=0,sy=0,tx=0,ty=0; int count=0;
        double cs=std::cos(theta), sn=std::sin(theta);
        // Accumulate moments for corresponding transformed source and target pairs.
        double xx=0,xy=0,yx=0,yy=0;
        for(int i=0;i<n;++i) {
            double px=cs*src[2*i]-sn*src[2*i+1]+x, py=sn*src[2*i]+cs*src[2*i+1]+y;
            double best=max_distance*max_distance; int jbest=-1;
            for(int j=0;j<m;++j) { double dx=px-dst[2*j], dy=py-dst[2*j+1], d=dx*dx+dy*dy; if(d<best){best=d;jbest=j;} }
            if(jbest<0) continue;
            double qx=dst[2*jbest], qy=dst[2*jbest+1];
            sx+=px; sy+=py; tx+=qx; ty+=qy; xx+=px*qx; xy+=px*qy; yx+=py*qx; yy+=py*qy; ++count;
        }
        if(count<3) return -2;
        double a=std::atan2(xy-yx-(sx*ty-sy*tx)/count, xx+yy-(sx*tx+sy*ty)/count);
        double c=std::cos(a), s=std::sin(a), dx=tx/count-(c*sx-s*sy)/count, dy=ty/count-(s*sx+c*sy)/count;
        double nx=c*x-s*y+dx, ny=s*x+c*y+dy; x=nx; y=ny; theta+=a;
        if(std::abs(a)+std::hypot(dx,dy)<1e-7) break;
    }
    out[0]=x; out[1]=y; out[2]=theta; return 0;
}
