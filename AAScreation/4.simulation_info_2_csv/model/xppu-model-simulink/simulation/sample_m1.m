tStart = tic;
s=1;
for a_acc=1:0.5:5.5
    for a_de=1:0.5:5.5
       for n=1:100
          dot_phi=n/100; %rad/s
          x(s)=dot_phi;
          a(s)=a_acc;
          b(s)=a_de;
          sim('simplify_dynamik_dchange');
          T=unique(time.Data(time.Data>0,1));
          if ~isempty(T)
             t_damp(s)=T(end);
          else
             t_damp(s)=0;
          end
          t_1(s)=t_damp(s)+(pi/2-0.5*dot_phi^2/a_de-0.5*dot_phi^2/a_acc)/dot_phi+dot_phi/a_acc; % s
%     E(n)=0.5*M*(0.5*L)^2*dot_phi^2+0.5*m*L^2*dot_phi^2; % J
          s=s+1;
       end
    end
end
tsum_1 = toc(tStart);
% figure(1);
% plot(x,t_1,x,t_damp,'--o');
% xlabel('dot_ phi [rad/s]');
% ylabel('t [s]'); 
% for i=1:length(x)
% text(x(i),t_1(i),num2str(t_1(i)));
% text(x(i),t_damp(i),num2str(t_damp(i)))
% end
% figure(2);
% plot(x,E,'--*');
% xlabel('dot_ phi [rad/s]');
% ylabel('E [J]'); 
% for i=1:length(x)
% text(x(i),E(i),num2str(E(i)))
% end