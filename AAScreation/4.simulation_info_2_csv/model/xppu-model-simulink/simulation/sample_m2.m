% for n=1:9 % solver ode15s
%     dot_phi_soll=n/20;
%     sim('dynamik_3');
%     T=unique(time.Data(time.Data>0,1));
%     if ~isempty(T)&&T(end)>pi/2/dot_phi_soll
%         t(n)=T(end);
%     else
%         t(n)=pi/2/dot_phi_soll;
%     end
%     x(n)=dot_phi_soll;
%     E(n)=0.5*Mass*(0.5*L)^2*dot_phi_soll^2+0.5*m*L^2*dot_phi_soll^2; % J
% end
%-------------------------------------------------------------
tStart_2 = tic;
s=1;
for a_acc=1:0.5:5.5   %ode45
    for a_de=1:0.5:5.5
      for n=1:100 % solver ode113s
        dot_phi_soll=n/100;
        o(s)=(pi/2-0.5*dot_phi_soll^2/a_de-0.5*dot_phi_soll^2/a_acc)/dot_phi_soll+dot_phi_soll/a_acc+dot_phi_soll/a_de;
        sim('dynamik_3');
        T=unique(time.Data(time.Data>0,1));
        if ~isempty(T)&&T(end)>o(s)
            t_2(s)=T(end);
        else
            t_2(s)=o(s);
        end
%     x(s)=dot_phi_soll;
%     E(s)=0.5*Mass*(0.5*L)^2*dot_phi_soll^2+0.5*m*L^2*dot_phi_soll^2; % J
        s=s+1;
      end
    end
end
tsum_2 = toc(tStart_2);
% figure(3);
% plot(x,o,x,t,'--o');
% xlabel('dot_ phi [rad/s]');
% ylabel('t [s]'); 
% for i=1:length(x)
% text(x(i),t(i),num2str(t(i)))
% end
% figure(4);
% plot(x,E,'--*');
% xlabel('dot_ phi [rad/s]');
% ylabel('E [J]'); 
% for i=1:length(x)
% text(x(i),E(i),num2str(E(i)))
% end