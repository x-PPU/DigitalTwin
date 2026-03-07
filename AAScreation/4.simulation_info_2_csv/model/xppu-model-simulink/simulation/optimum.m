data=xlsread('sample_rising.xls');
sample_M2=data(:,5);
batch=10;
size=1000;
iteration=10;
point=10; %sample point
total=point*batch;
for i=1:batch
    A(:,i)=sample_M2((i-1)*size+1:i*size,1);
    n=randi(1000,point,1);
    average(1,i)=mean(A(n,i)); 
    standard(1,i)=std(A(n,i));
end

%iteration 1
N(1,1)=standard(1,1)*sqrt(sum(point^2./standard(1,:).^2)-point^2./standard(1,1)^2);
N(1,1)=round(N(1,1));
if N(1,1)==1
        N(1,1)=N(1,1)+1;
elseif N(1,1)==0
        N(1,1)=N(1,1)+2;
else
end
a(2)=1; %proportion
b=((average(1,1)-average(1,2))/standard(1,2))^2;
for i=3:batch
    a(i)=b/((average(1,1)-average(1,i))/standard(1,i))^2;
end
a_sum=sum(a);
for i=2:batch
    N(1,i)=(total-N(1,1))*a(i)/a_sum;
    N(1,i)=round(N(1,i));
    if N(1,i)==1
        N(1,i)=N(1,i)+1;
    elseif N(1,i)==0
        N(1,i)=N(1,i)+2;
    else
    end
end

for i=1:batch
%     M(1:N(1,i),i)=A(1:N(1,i),i);
      n=randi(1000,N(1,i),1);
      M(1:N(1,i),i)=A(n,i);
end
M(M==0)=inf;
M_min(1)=min(min(M));

%iteration i
for it=2:iteration
  for i=1:batch
%      n=randi(1000,N(it-1,i),1);
     average(it,i)=mean(M(1:N(it-1,i),i)); 
     standard(it,i)=std(M(1:N(it-1,i),i));
%      average(it,i)=mean(A(n,i)); 
%      standard(it,i)=std(A(n,i));
  end
  N(it,1)=standard(it,1)*sqrt(sum(N(it-1,:).^2./standard(it,:).^2)-N(it-1,1).^2./standard(it,1)^2);
  N(it,1)=round(N(it,1));
  if N(it,1)==1
        N(it,1)=N(it,1)+1;
  elseif N(it,1)==0
        N(it,1)=N(it,1)+2;
  else
  end
  a(2)=1; %proportion
  b=((average(it,1)-average(it,2))/standard(it,2))^2;
  for i=3:batch
      a(i)=b/((average(it,1)-average(it,i))/standard(it,i))^2;
  end
  a_sum=sum(a);
  for i=2:batch
     N(it,i)=(total-N(it,1))*a(i)/a_sum;
     N(it,i)=round(N(it,i));
     if N(it,i)==1
        N(it,i)=N(it,i)+1;
     elseif N(it,i)==0
        N(it,i)=N(it,i)+2;
     else
     end
  end
  N=round(N);
  for i=1:batch
      n=randi(1000,N(it,i),1);
      M(1:N(it,i),i)=A(n,i);
%     M(1:N(it,i),i)=A(N(it-1,i)+1:N(it-1,i)+N(it,i),i);
  end
  M(M==0)=inf;
  M_min(it)=min(min(M));
  if M_min(it)>=M_min(it-1)
      M_min(it)=M_min(it-1);
  end
end
figure(2);
plot(100:100:1000,M_min);