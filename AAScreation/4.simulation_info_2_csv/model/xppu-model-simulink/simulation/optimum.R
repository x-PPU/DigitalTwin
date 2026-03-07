fms=read.csv('D:/sample/sample_rising.csv')
f=cbind(fms[1:78,5],fms[79:156,5],fms[157:234,5],fms[235:312,5],fms[313:390,5],fms[391:468,5],fms[469:546,5],fms[547:624,5],fms[625:702,5],fms[703:780,5])
batch=10
l=rep(78,10)
o=matrix(0,nrow=10000,ncol=200)
for(b in 1:10000)
{
 g=f
 m=rep(0,batch)
 n0=3
 al=rep(0,batch)
 va=rep(0,batch)
 ns=rep(0,batch)
 ss=matrix(0,nrow=200,ncol=batch)
 for(i in 1:batch)
  { 
  	s=rep(0,n0)
    for(j in 1:n0)
     {
       r=floor(runif(1)*(l[i]-j+1)+1)
       s[j]=g[1:(l[i]-j+1),i][r]
       g[1:(l[i]-j),i]=g[1:(l[i]-j+1),i][-r]
     }
  m[i]=min(s)
  ss[1:n0,i]=s
  al[i]=mean(s)
  va[i]=var(s)
  }
 o[b,30]=min(m)
 index=which(al==min(al))
 ratio=va/(al[index]-al)^2
 ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
 n_0=rep(n0,batch)
 ns=31*ratio/sum(ratio)
 s_next=which((ns-n_0)==max(ns-n_0))
 size=l-n_0
 I=rep(0,batch)
 for(t in seq(31,200,1))
  {
   if(size[s_next]>0)
   {
  	 if(I[s_next]==0)
  	 {
  	 	r=floor(runif(1)*(size[s_next])+1)
  	 	I[s_next]=1
  	 }
  	 else
  	 {
  	 	r=1
  	 	I[s_next]=0
  	 } 	 
   	 s=g[1:(size[s_next]),s_next][r]
   	 if(size[s_next]>1)
   	    g[1:(size[s_next]-1),s_next]=g[1:(size[s_next]),s_next][-r]
   	 m[s_next]=min(s,m[s_next])
   	 ss[(n_0[s_next]+1),s_next]=s
     al[s_next]=mean(ss[1:(n_0[s_next]+1),s_next])
     va[s_next]=var(ss[1:(n_0[s_next]+1),s_next])
     size[s_next]=size[s_next]-1
     n_0[s_next]=n_0[s_next]+1
     o[b,t]=min(m)
     index=which(al==min(al))
     ratio=va/(al[index]-al)^2
     ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
     ns=(t+1)*ratio/sum(ratio)
     s_next=which(rank(ns-n_0,ties.method="first")==batch)
     for(k in 1:(batch-1))
     {
     	if(size[s_next]==0)
     	  s_next=which(rank(ns-n_0,ties.method="first")==batch-k)
     }
   }
  }
}
o_mean=rep(0,200)
for(i in seq(30,200,10))
{o_mean[i]=mean(o[,i])}
write.csv(data.frame(o_mean[seq(30,200,10)]),file="D:/sample/4.csv")

**multimodal 1**
a=9
x=seq(0,100,0.1)
f_x=(sin(a/100*pi*x))^6/2^(2*((x-10)/80)^2)+0.1*cos(0.5*pi*x)+0.5*((x-40)/60)^2+0.4*sin((x+10)/100*pi)
g_x=(sin(a/100*pi*x))^6/2^(2*((x-10)/80)^2)
g_o=g_x[order(g_x)]
f_o=f_x[order(g_x)]

f=matrix(0,nrow=101,ncol=10)
for(i in 1:9)
{
	f[1:100,i]=f_o[((i-1)*100+1):(i*100)]
}
f[,10]=f_o[901:1001]
batch=10
l=c(rep(100,9),101)
o=matrix(0,nrow=10000,ncol=50)
for(b in 1:10000)
{
 g=f
 m=rep(0,batch)
 n0=2
 al=rep(0,batch)
 va=rep(0,batch)
 ns=rep(0,batch)
 ss=matrix(0,nrow=110,ncol=batch)
 for(i in 1:batch)
  { 
  	s=rep(0,n0)
    for(j in 1:n0)
     {
       r=floor(runif(1)*(l[i]-j+1)+1)
       s[j]=g[1:(l[i]-j+1),i][r]
       g[1:(l[i]-j),i]=g[1:(l[i]-j+1),i][-r]
     }
  m[i]=max(s)
  ss[1:n0,i]=s
  al[i]=mean(s)
  va[i]=var(s)
  }
 o[b,20]=max(m)
 index=which(al==max(al))
 ratio=va/(al[index]-al)^2
 ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
 n_0=rep(n0,batch)
 ns=21*ratio/sum(ratio)
 s_next=which((ns-n_0)==max(ns-n_0))
 size=l-n_0
 I=rep(0,batch)
 for(t in seq(21,110,1))
  {
   if(size[s_next]>0)
   {
  	 if(I[s_next]==0)
  	 {
  	 	r=floor(runif(1)*(size[s_next])+1)
  	 	I[s_next]=1
  	 }
  	 else
  	 {
  	 	r=1
  	 	I[s_next]=0
  	 } 	 
   	 s=g[1:(size[s_next]),s_next][r]
   	 if(size[s_next]>1)
   	    g[1:(size[s_next]-1),s_next]=g[1:(size[s_next]),s_next][-r]
   	 m[s_next]=max(s,m[s_next])
   	 ss[(n_0[s_next]+1),s_next]=s
     al[s_next]=mean(ss[1:(n_0[s_next]+1),s_next])
     va[s_next]=var(ss[1:(n_0[s_next]+1),s_next])
     size[s_next]=size[s_next]-1
     n_0[s_next]=n_0[s_next]+1
     o[b,t]=max(m)
     index=which(al==max(al))
     ratio=va/(al[index]-al)^2
     ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
     ns=(t+1)*ratio/sum(ratio)
     s_next=which(rank(ns-n_0,ties.method="first")==batch)
     for(k in 1:(batch-1))
     {
     	if(size[s_next]==0)
     	  s_next=which(rank(ns-n_0,ties.method="first")==batch-k)
     }
   }
  }
}
o_mean=rep(0,110)
for(i in seq(20,110,10))
{o_mean[i]=mean(o[,i])}
write.csv(data.frame(o_mean[seq(20,110,10)]),file="D:/sample/4.csv")

**multimodal 2**
a=9
x=seq(0,100,0.1)
f_x=(sin(a/100*pi*x))^6/2^(2*((x-10)/80)^2)+0.1*cos(0.5*pi*x)+0.5*((x-40)/60)^2+0.4*sin((x+10)/100*pi)
g_x=(sin(a/100*pi*(x-1.2)))^6/2^(2*((x-10)/80)^2)
g_o=g_x[order(g_x)]
f_o=f_x[order(g_x)]
f=matrix(0,nrow=101,ncol=10)
for(i in 1:9)
{
	f[1:100,i]=f_o[((i-1)*100+1):(i*100)]
}
f[,10]=f_o[901:1001]
batch=10
l=c(rep(100,9),101)
o=matrix(0,nrow=10000,ncol=71)
for(b in 1:10000)
{
 g=f
 m=rep(0,batch)
 n0=3
 al=rep(0,batch)
 va=rep(0,batch)
 ns=rep(0,batch)
 ss=matrix(0,nrow=71,ncol=batch)
 for(i in 1:batch)
  { 
  	s=rep(0,n0)
    for(j in 1:n0)
     {
       r=floor(runif(1)*(l[i]-j+1)+1)
       s[j]=g[1:(l[i]-j+1),i][r]
       g[1:(l[i]-j),i]=g[1:(l[i]-j+1),i][-r]
     }
  m[i]=max(s)
  ss[1:n0,i]=s
  al[i]=mean(s)
  va[i]=var(s)
  }
 o[b,30]=max(m)
 index=which(al==max(al))
 ratio=va/(al[index]-al)^2
 ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
 n_0=rep(n0,batch)
 ns=31*ratio/sum(ratio)
 s_next=which((ns-n_0)==max(ns-n_0))
 size=l-n_0
 I=rep(0,batch)
 for(t in seq(31,71,1))
  {
   if(size[s_next]>0)
   {
  	 if(I[s_next]==0)
  	 {
  	 	r=floor(runif(1)*(size[s_next])+1)
  	 	I[s_next]=1
  	 }
  	 else
  	 {
  	 	r=1
  	 	I[s_next]=0
  	 } 	 
   	 s=g[1:(size[s_next]),s_next][r]
   	 if(size[s_next]>1)
   	    g[1:(size[s_next]-1),s_next]=g[1:(size[s_next]),s_next][-r]
   	 m[s_next]=max(s,m[s_next])
   	 ss[(n_0[s_next]+1),s_next]=s
     al[s_next]=mean(ss[1:(n_0[s_next]+1),s_next])
     va[s_next]=var(ss[1:(n_0[s_next]+1),s_next])
     size[s_next]=size[s_next]-1
     n_0[s_next]=n_0[s_next]+1
     o[b,t]=max(m)
     index=which(al==max(al))
     ratio=va/(al[index]-al)^2
     ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
     ns=(t+1)*ratio/sum(ratio)
     s_next=which(rank(ns-n_0,ties.method="first")==batch)
     for(k in 1:(batch-1))
     {
     	if(size[s_next]==0)
     	  s_next=which(rank(ns-n_0,ties.method="first")==batch-k)
     }
   }
  }
}
o_mean=rep(0,71)
for(i in seq(30,71,1))
{o_mean[i]=mean(o[,i])}
write.csv(data.frame(o_mean[seq(30,71,1)]),file="D:/sample/4.csv")

**multimodal 3**
a=9
x=seq(0,100,0.1)
f_x=(sin(a/100*pi*x))^6/2^(2*((x-10)/80)^2)+0.1*cos(0.5*pi*x)+0.5*((x-40)/60)^2+0.4*sin((x+10)/100*pi)
g_x=(sin(a/100*pi*(x-5)))^6/2^(2*((x-10)/80)^2)
g_o=g_x[order(g_x)]
f_o=f_x[order(g_x)]
f=matrix(0,nrow=101,ncol=10)
for(i in 1:9)
{
	f[1:100,i]=f_o[((i-1)*100+1):(i*100)]
}
f[,10]=f_o[901:1001]
batch=10
l=c(rep(100,9),101)
o=matrix(0,nrow=10000,ncol=71)
for(b in 1:10000)
{
 g=f
 m=rep(0,batch)
 n0=3
 al=rep(0,batch)
 va=rep(0,batch)
 ns=rep(0,batch)
 ss=matrix(0,nrow=71,ncol=batch)
 for(i in 1:batch)
  { 
  	s=rep(0,n0)
    for(j in 1:n0)
     {
       r=floor(runif(1)*(l[i]-j+1)+1)
       s[j]=g[1:(l[i]-j+1),i][r]
       g[1:(l[i]-j),i]=g[1:(l[i]-j+1),i][-r]
     }
  m[i]=max(s)
  ss[1:n0,i]=s
  al[i]=mean(s)
  va[i]=var(s)
  }
 o[b,30]=max(m)
 index=which(al==max(al))
 ratio=va/(al[index]-al)^2
 ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
 n_0=rep(n0,batch)
 ns=31*ratio/sum(ratio)
 s_next=which((ns-n_0)==max(ns-n_0))
 size=l-n_0
 I=rep(0,batch)
 for(t in seq(31,71,1))
  {
   if(size[s_next]>0)
   {
  	 if(I[s_next]==0)
  	 {
  	 	r=floor(runif(1)*(size[s_next])+1)
  	 	I[s_next]=1
  	 }
  	 else
  	 {
  	 	r=1
  	 	I[s_next]=0
  	 } 	 
   	 s=g[1:(size[s_next]),s_next][r]
   	 if(size[s_next]>1)
   	    g[1:(size[s_next]-1),s_next]=g[1:(size[s_next]),s_next][-r]
   	 m[s_next]=max(s,m[s_next])
   	 ss[(n_0[s_next]+1),s_next]=s
     al[s_next]=mean(ss[1:(n_0[s_next]+1),s_next])
     va[s_next]=var(ss[1:(n_0[s_next]+1),s_next])
     size[s_next]=size[s_next]-1
     n_0[s_next]=n_0[s_next]+1
     o[b,t]=max(m)
     index=which(al==max(al))
     ratio=va/(al[index]-al)^2
     ratio[index]=sqrt(va[index]*sum((ratio[-index])^2/va[-index]))
     ns=(t+1)*ratio/sum(ratio)
     s_next=which(rank(ns-n_0,ties.method="first")==batch)
     for(k in 1:(batch-1))
     {
     	if(size[s_next]==0)
     	  s_next=which(rank(ns-n_0,ties.method="first")==batch-k)
     }
   }
  }
}
o_mean=rep(0,71)
for(i in seq(30,71,1))
{o_mean[i]=mean(o[,i])}
write.csv(data.frame(o_mean[seq(30,71,1)]),file="D:/sample/4.csv")

